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
            #'style': 'fill: none'},
            'style': 'fill: #f00'},
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

    def add_entity(self, class_type, **data) -> Svg_entity:
        entity = class_type(**data, container = self)
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

    def __init__(self, points: list[tuple[float]], container: Svg_container): 
        self.points = points
        self.container = container
        self.drawing = container.drawing
        Svg_entity.__init__(self, 
                entity_type = 'polyline',
                obj = container.drawing.obj.polyline(points = self.points)
                )

class Path(Svg_graphics):
    obj: svgwrite.path.Path

    def __init__(self, 
            coords_string: str, 
            coords_values: list[tuple[float]], 
            container: Svg_container): 
        self.container = container
        self.drawing = container.drawing
        self.points = coords_values
        Svg_entity.__init__(self, 
                entity_type = 'path',
                obj = container.drawing.obj.path(coords_string)
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
