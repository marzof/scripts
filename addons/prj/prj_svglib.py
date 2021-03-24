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
from prj import prj_utils
from svgwrite.extensions import Inkscape


tuple_points = lambda x: [tuple([float(n) for n in i.split(',')]) 
        for i in x.split(' ')]
get_xml_elements = lambda container, element: list(
        container.iterdescendants(element))
get_pl_points = lambda polylines: [tuple_points(pt.attrib['points']) 
        for pt in polylines]
scale_move_round_points = lambda points, scale, offset, rnd: numpy.round(
        numpy.multiply([numpy.subtract(p, offset) for p in points], scale), rnd)
flatten = lambda t: [item for sublist in t for item in sublist]

RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

class Svg_drawing:
    original_svg : svgutils.compose.SVG
    ROUNDING: int = 4

    def __init__(self, filepath: str, context: Drawing_context, subject: str):
        print('start svg')
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

    def __write(self, size: tuple[float], 
            subject: svgutils.compose.Element) -> svgwrite.drawing.Drawing:
        """ Write svg with subject scaled to fit size and offset """

        drawing = svgwrite.drawing.Drawing(filename= self.path + '_edit.svg',
                size=(str(self.px2mm(size))+'mm', str(self.px2mm(size)) + 'mm'))
        ink_drawing = Inkscape(drawing)

        layers = [*self.layers]
        if 'cut' in self.layers:
            prj_utils.move_to_last('cut', layers)

        ## TODO clean up
        layer_objs = []
        for layer in layers:
            pts = self.__transfer_points(layer, self.offset)
            if layer == 'cut':
                pts_dict = self.__split_and_collect(pts)
                cut_polylines = self.__reshape_polylines(pts_dict)
                pts = [cut_pl for cut_pl in cut_polylines]
            layer_objs.append(Layer(
                name = layer, 
                drawing = drawing,
                layer = ink_drawing.layer(label=layer), 
                points = pts
                ))
            drawing.add(layer_objs[-1].layer)

        drawing.save(pretty=True)
        return drawing



    def __transfer_points(self, layer: str, offset: tuple[float]) -> \
            list[tuple[tuple]]:
        """ Get polylines points, scale, move and round them 
        and return as list of tuples """
        polylines = get_xml_elements(self.layers[layer], 'polyline')
        pl_points = get_pl_points(polylines)
        smrp = [scale_move_round_points(pl_p, self.unit_to_px_factor, 
            offset, self.ROUNDING) for pl_p in pl_points]
        return [tuple(map(tuple, p)) for p in smrp]

    def __split_and_collect(self, points: list[tuple[tuple]]) -> \
            dict[tuple[int],list[int]]:
        """ Break polylines into 2-points segments and populate a dict """
        dic = {}
        points2couples = {pl_id: [(pl_pts[i], pl_pts[i+1]) for i in 
            range(len(pl_pts)-1)] for pl_id, pl_pts in enumerate(points)}
        points = [(pt, pl) for pl in points2couples 
            for pt_couple in points2couples[pl] for pt in pt_couple]
        for pl_idx, pt_pl in enumerate(points):
            idx = pl_idx//2
            pt, pl = pt_pl[0], pt_pl[1]
            prj_utils.put_in_dict(dic, pt, idx)
            if len(dic[pt]) > 2:
                ## Add a third value to distinguish points with
                ## three or more lines pointing to them
                dic[pt].remove(idx)
                pt += (pl,)
                prj_utils.put_in_dict(dic, pt, idx)
        return dic

    def __frame_loc_size(self, frame_name: str) -> \
            tuple[tuple[float],list[float]]: 
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

    def __reshape_polylines(self, pts_dict):
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
        return cut_polylines


class Layer:
    ## TODO clean up and rationalize

    polylines: list

    def __init__(self, name, drawing, layer, points):
        self.name = name
        self.drawing = drawing
        self.layer = layer
        self.points = points

        self.polylines = self.add_polylines()
        for pl in self.polylines:
            self.layer.add(pl)

    def add_polylines(self):
        pl_list = []
        fill = '#f00' if self.name == 'cut' else 'none'
        for id_no, pl_pts in enumerate(self.points):
            pl_list.append(self.drawing.polyline(points = pl_pts))
            pl_list[-1].update({'stroke': '#000000', 'stroke-opacity': '1', 
                    'id': 'pl' + str(id_no), 'stroke-linecap': 'round', 
                    'stroke-width': '.1', 'style': 'fill: ' + fill})
        return pl_list
