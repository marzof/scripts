#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 


import svgwrite
import svgutils
#import xml.etree.ElementTree as ET
import numpy
import math
import re
import prj
from prj.prj_drawing_classes import Drawing_context
from svgwrite.extensions import Inkscape


tuple_points = lambda x: [tuple([float(n) for n in i.split(',')]) 
        for i in x.split(' ')]
get_xml_elements = lambda container, element: list(
        container.iterdescendants(element))
get_pl_points = lambda polylines: [tuple_points(pt.attrib['points']) 
        for pt in polylines]
scale_move_round_points = lambda points, scale, offset, rnd: numpy.round(
        numpy.multiply([numpy.subtract(p, offset) for p in points], scale), rnd)

RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

class Svg_drawing:
    original_svg : svgutils.compose.SVG

    def __init__(self, filepath: str, context: Drawing_context, subject: str):
        self.path = filepath
        self.original_svg = svgutils.compose.SVG(filepath)
        self.drawing_context = context

        subject_name = prj.SVG_GROUP_PREFIX + subject
        frame_name = prj.SVG_GROUP_PREFIX + context.FRAME_NAME
        base_offset, base_size = self.__frame_loc_size(frame_name)
        base_ratio = context.frame_size / base_size[0]

        self.offset = base_offset
        self.px_to_mm_factor = 10 * base_ratio
        self.unit_to_px_factor = RESOLUTION_FACTOR * base_ratio
        self.px2mm = lambda x: self.px_to_mm_factor * x
        self.subject = self.original_svg.find_id(subject_name)
        self.layers = {}
        for g in get_xml_elements(self.subject.root, 'g'):
            g_id = g.attrib['id']
            if g_id in [prj.STYLES[style]['name'] for style in prj.STYLES]:
                self.layers[g_id] = g
        self.svg = self.__write(size=base_size[0], subject=self.layers)

    def __transfer_points(self, layer, offset):
        """ Get polylines points, scale, move and round them 
        and return as list of tuples """
        polylines = get_xml_elements(self.layers[layer], 'polyline')
        pl_points = get_pl_points(polylines)
        smrp = [scale_move_round_points(pl_p, self.unit_to_px_factor, 
            offset, 4) for pl_p in pl_points]
        return [tuple(map(tuple, p)) for p in smrp]

    def __write(self, size: tuple[float], 
            subject: svgutils.compose.Element) -> svgwrite.drawing.Drawing:
        """ Write svg with subject scaled to fit size and offset """
        drawing = svgwrite.drawing.Drawing(filename= self.path + '_edit.svg',
                size=(str(self.px2mm(size)) + 'mm', str(self.px2mm(size)) + 'mm'))
        ink_drawing = Inkscape(drawing)

        layers = [*self.layers]
        if 'cut' in self.layers:
            layers.remove('cut')

        for layer in layers:
            style_layer = ink_drawing.layer(label=layer)

            points = self.__transfer_points(layer, self.offset)

            for id_no, pl_pts in enumerate(points):
                polyline = drawing.polyline(points = pl_pts)
                polyline.update({'stroke': '#000000', 'stroke-opacity': '1', 
                        'id': 'pl' + str(id_no), 'stroke-linecap': 'round', 
                        'stroke-width': '.1', 'style': 'fill: none'})
                style_layer.add(polyline)

            drawing.add(style_layer)

        ################### PREPARE CUT ####################
        if 'cut' in self.layers:
            layer = 'cut'
            cut_layer = ink_drawing.layer(label=layer)

            points = self.__transfer_points(layer, self.offset)

            ## Break polylines into 2-points segments and populate pts_dict
            pts_dict = {}
            cut_pl_no = 0
            for id_no, pl_pts in enumerate(points):
                pts_couples = [(pl_pts[i], pl_pts[i+1]) 
                        for i in range(len(pl_pts)-1)]
                for couple in pts_couples:
                    for po in couple:
                        if po not in pts_dict:
                            pts_dict[po] = [cut_pl_no]
                        elif len(pts_dict[po]) < 2:
                            pts_dict[po].append(cut_pl_no)
                        ## Add a third value to distinguish points with
                        ## three or more lines pointing to them
                        elif po + (id_no,) not in pts_dict:
                            pts_dict[po + (id_no,)] = [cut_pl_no]
                        else:
                            pts_dict[po + (id_no,)].append(cut_pl_no)
                    cut_pl_no += 1

            ## Reconnect segments from points in pts_dict
            cut_polylines = []
            pl_ids = list(range(len(pts_dict)))
            ordered_pts = []
            pl_id = pl_ids[0] 
            starts_with = [pt for pt, idx in pts_dict.items()][0]
            while len(pts_dict) > 0:
                ## If cut object is composed by multiple closed elements 
                ## it needs to restart from another point (pl_id)
                if pl_id not in pl_ids:
                    ## Save last ordered list of points and start a new one
                    cut_polylines.append(ordered_pts)
                    ordered_pts = []
                    pl_id = pl_ids[0] 
                    starts_with = [pt for pt, idx in pts_dict.items()][0]
                for pt, idx in pts_dict.items():
                    if pl_id in idx:
                        ## Some pt could contain more than 2 value: 
                        ## need just the first two
                        ordered_pts.append((pt[0], pt[1]))
                        pl_ids.remove(pl_id)
                        pl_id = [v for v in pts_dict[pt][:2] if v != pl_id][0]
                        break
                del(pts_dict[pt])
            ## Close last perimeter connecting to starting point
            ordered_pts.append(starts_with)
            cut_polylines.append(ordered_pts)

            for cut_pl in cut_polylines:
                polyline = drawing.polyline(points = cut_pl)
                polyline.update({'stroke': '#000000', 'stroke-opacity': '1', 
                        'id': 'pl', 'stroke-linecap': 'round', 
                        'stroke-width': '.35', 'style': 'fill: #f00'})
                cut_layer.add(polyline)
            drawing.add(cut_layer)
        ################ END CUT ###################

        drawing.save(pretty=True)
        return drawing


    def __frame_loc_size(self, frame_name: str) -> tuple[tuple[float],list[float]]: 
        """ Get dimensions of rect in svg """
        min_val, max_val = math.inf, 0.0
        g = self.original_svg.find_id(frame_name)
        pl = get_xml_elements(g.root, 'polyline')
        pts = get_pl_points(pl)
        for p in pts:
            for co in p:
                if sum(co) < min_val:
                    min_val = sum(co)
                    origin = co
                if sum(co) > max_val:
                    max_val = sum(co)
                    extension = co
        size = numpy.subtract(extension, origin)
        return origin, size 

