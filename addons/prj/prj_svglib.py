#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 


import svgwrite
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


POLYLINE_TAG: str = 'polyline'
SVG_ATTRIBUTES = {
        'prj': {'stroke': '#000000', 'stroke-opacity': '1',
            'stroke-linecap': 'round', 'stroke-width': '.1', 
            'style': 'fill: none'},
        'cut': {'stroke': '#000000', 'stroke-opacity': '1',
            'stroke-linecap': 'round', 'stroke-width': '.35', 
            'style': 'fill: none'},
            #'style': 'fill: #f00'},
        }

class Svg_entity:
    obj: svgwrite.base.BaseElement

    def __init__(self, entity_type, obj):
        self.type: str = entity_type
        self.obj = obj

class Svg_container(Svg_entity):
    entities: dict[str,list[svgwrite.base.BaseElement]]

    def __init__(self):
        self.entities = {}

    def drawing_container(self, container: 'Svg_container') -> 'Svg_drawing':
        if isinstance(container, Svg_drawing):
            return container
        return self.drawing_container(container.container)

    def add_entity(self, class_type, data) -> Svg_entity:
        entity = class_type(data, self)
        if entity.type not in entity.container.entities:
            entity.container.entities[entity.type] = []
        entity.container.entities[entity.type].append(entity)
        self.obj.add(entity.obj)
        return entity

class Svg_graphics(Svg_entity):

    def set_attribute(self, dic: dict[str, str]) -> None:
        self.obj.update(dic)


class Layer(Svg_container):
    drawing: 'Svg_drawing'
    obj: svgwrite.container.Group

    def __init__(self, label: str, container: Svg_container):
        Svg_container.__init__(self)
        self.label = label
        self.container = container
        self.drawing = self.drawing_container(self.container)
        Svg_entity.__init__(self, 
                entity_type = 'layer',
                obj = Inkscape(self.drawing.obj).layer(label=label)
                )

class Polyline(Svg_graphics):
    obj: svgwrite.shapes.Polyline

    def __init__(self, points: list[list[float]], container: Svg_container): 
        self.points = points
        self.container = container
        self.drawing = container.drawing
        Svg_entity.__init__(self, 
                entity_type = 'polyline',
                obj = container.drawing.obj.polyline(points = self.points)
                )

class Path(Svg_graphics):
    obj: svgwrite.path.Path

    def __init__(self, coords, container: Svg_container): 
        self.container = container
        self.drawing = container.drawing
        Svg_entity.__init__(self, 
                entity_type = 'path',
                obj = container.drawing.obj.path(coords)
                )

class Svg_drawing(Svg_container):

    def __init__(self, filepath: str, size = ('100mm', '100mm')):
        Svg_container.__init__(self)
        self.path = filepath
        self.size = size
        self.drawing = self

    def __enter__(self) -> 'Svg_drawing':
        self.obj = svgwrite.drawing.Drawing(
                filename= self.path + '_edit.svg', size=self.size)
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.obj.save(pretty=True)


        #subject_name = prj.SVG_GROUP_PREFIX + subject
        ####### Pass to main ->
        #frame_name = prj.SVG_GROUP_PREFIX + context.FRAME_NAME
        #frame = self.original_svg.find_id(frame_name)
        #base_offset, base_size = get_rect_dimensions(frame)
        #base_ratio = context.frame_size / base_size[0]

        #self.offset = base_offset
        #self.px_to_mm_factor = 10 * base_ratio
        #self.unit_to_px_factor = RESOLUTION_FACTOR * base_ratio
        #self.px2mm = lambda x: self.px_to_mm_factor * x
        ######## <-
        #self.subject = self.original_svg.find_id(subject_name)
        #self.original_layers = {}
        #for g in get_xml_elements(self.subject.root, 'g'):
        #    g_id = g.attrib['id']
        #    if g_id in [prj.STYLES[style]['name'] for style in prj.STYLES]:
        #        self.original_layers[g_id] = g
        #self.layers = {}
        #self.svg = self.__write(size=base_size[0], subject=self.original_layers)

    ## TODO add method to convert polylines to paths 
    ## see https://developer.mozilla.org/en-US/docs/Web/SVG/Tutorial/Paths
    # def __write(self, size: tuple[float], 
    #         subject: svgutils.compose.Element) -> svgwrite.drawing.Drawing:
    #     """ Write svg with subject scaled to fit size and offset """

    #     drawing = svgwrite.drawing.Drawing(filename= self.path + '_edit.svg',
    #             size=(str(self.px2mm(size))+'mm', str(self.px2mm(size)) + 'mm'))
    #     ink_drawing = Inkscape(drawing)

    #     layer_labels = prj_utils.move_to_last('cut', [*self.original_layers])

    #     for layer_label in layer_labels:
    #         lay = Layer(label = layer_label, drawing = drawing,
    #             layer = ink_drawing.layer(label=layer_label))
    #         self.layers[lay.label] = lay

    #         polylines_xml = get_xml_elements(self.original_layers[lay.label], 
    #                 POLYLINE_TAG)
    #         layer_points = relocate_points(polylines_xml, 
    #                 self.unit_to_px_factor, self.offset, self.ROUNDING)

    #         for polyline_points in layer_points:
    #             pl = Polyline(polyline_points, drawing, lay)
    #             pl.set_attribute(attributes(pl.id)[lay.label])
    #             prj_utils.put_in_dict(lay.entities, POLYLINE_TAG, pl)

    #         if lay.label == 'cut':
    #             lay.entities[POLYLINE_TAG] = join_polylines(
    #                     lay.entities[POLYLINE_TAG], drawing, lay)
    #         for pl in lay.entities[POLYLINE_TAG]:
    #             lay.layer.add(pl.polyline)
    #         drawing.add(lay.layer)

    #     drawing.save(pretty=True)
    #     return drawing






def join_polylines(pl_list: list[Polyline], drawing: svgwrite.drawing.Drawing, 
        layer: Layer) -> list[Polyline]:
    joined_pl = []
    pl_points = [pl.points for pl in pl_list]
    points_polylines_dict = __split_and_collect(pl_points)
    cut_polylines_points = __reshape_polylines(points_polylines_dict)
    for polyline in cut_polylines_points:
        pl = Polyline(polyline, drawing, layer)
        pl.set_attribute(attributes('pl')[layer.label])
        joined_pl.append(pl)
    return joined_pl

## TODO revision this one only
def __reshape_polylines(pts_dict: dict[tuple[float],list[int]]) -> \
        list[list[tuple[float]]]:
    """ Reconnect segments from points in pts_dict """
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

def __split_and_collect(pl_points: list[tuple[tuple]]) -> \
        dict[tuple[float],list[int]]:
    """ Break polylines into 2-points segments and populate a dict """
    dic = {}
    two_points_split_dict = {pl_id: [(pl_pts[i], pl_pts[i+1]) for i in 
        range(len(pl_pts)-1)] for pl_id, pl_pts in enumerate(pl_points)}
    point_polyline_tuples = [(pt, pl) for pl in two_points_split_dict 
        for pt_couple in two_points_split_dict[pl] for pt in pt_couple]
    for pl_idx, pt_pl in enumerate(point_polyline_tuples):
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

## To archive
def get_rect_dimensions(rect) -> tuple[tuple[float], list[float]]: 
    """ Get dimensions of polyline rect in svg """
    min_val, max_val = math.inf, 0.0
    polylines = get_xml_elements(rect.root, POLYLINE_TAG)
    points = get_pl_points(polylines)
    point_coords = [co for p in points for co in p]
    for co in point_coords:
        if sum(co) < min_val:
            min_val, origin = sum(co), co
        if sum(co) > max_val:
            max_val, extension = sum(co), co
    size = numpy.subtract(extension, origin)
    return origin, size 
