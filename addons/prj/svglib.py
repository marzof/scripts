#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import re
import os
import numpy, math
import svgwrite
from svgwrite.extensions import Inkscape
import xml.etree.ElementTree as ET
from prj import BASE_CSS, SVG_ID, ROUNDING


POLYLINE_TAG: str = 'polyline'
PL_TAG = '{http://www.w3.org/2000/svg}polyline'
G_TAG = '{http://www.w3.org/2000/svg}g'
SVG_ATTRIBUTES = {'prj': {}, 'cut': {}, 'hid': {}, 'bak': {}}
        ## Set by style
        #'prj': {'stroke': '#000000', 'stroke-opacity': '1',
        #    'stroke-linecap': 'round', 'stroke-width': '.1', 
        #    'style': 'fill: none'},
        #'cut': {'stroke': '#000000', 'stroke-opacity': '1',
        #    'stroke-linecap': 'round', 'stroke-width': '.35', 
        #    'style': 'fill: #f00'},
        #'hid': {'stroke': '#808080', 'stroke-opacity': '1',
        #    'stroke-linecap': 'round', 'stroke-width': '.1', 
        #    'stroke-dasharray': (0.8, 0.4), 'style': 'fill: none'}, }

# # # # CLASSES # # # #

class Svg_entity:
    obj: svgwrite.base.BaseElement

    def __init__(self, entity_type, obj):
        self.type: str = entity_type
        self.obj = obj
        self.classes = ''
        
    def set_id(self, entity_id: str):
        self.obj.__setitem__('id', entity_id)
        self.id = entity_id
        return self.id

    def add_class(self, entity_class: str):
        update_class = f'{self.classes} {entity_class}'.strip()
        self.obj.__setitem__('class', update_class)
        self.classes = update_class
        return self.classes

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

class Use(Svg_container):
    drawing: 'Svg_drawing'
    obj: svgwrite.container.Use

    def __init__(self, link: str, container: Svg_container):
        self.container = container
        self.drawing = container.drawing
        self.link = link
        Svg_entity.__init__(self, 
                entity_type = 'use',
                obj = container.drawing.obj.use(href = link)
                )

    def add_entity(self, link: str) -> 'Use':
        self.link = link
        return self

class Style(Svg_container):
    drawing: 'Svg_drawing'
    obj: svgwrite.container.Style

    def __init__(self, content: str, container: Svg_container):
        Svg_container.__init__(self)
        self.content = content if content else ''
        self.container = container
        self.drawing = self.drawing_container(self.container)
        Svg_entity.__init__(self, 
                entity_type = 'style',
                obj = container.drawing.obj.style(content)
                )

        def add_entity(self, content: str) -> 'Style':
            self.content += content
            return self

        def replace_content(self, content: str) -> 'Style':
            self.content = content
            return self

class Group(Svg_container):
    drawing: 'Svg_drawing'
    obj: svgwrite.container.Group

    def __init__(self, container: Svg_container):
        Svg_container.__init__(self)
        self.container = container
        self.drawing = self.drawing_container(self.container)
        Svg_entity.__init__(self, 
                entity_type = 'group',
                obj = container.drawing.obj.g()
                )

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
                filename= self.path, size=self.size)
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.obj.save(pretty=True)
# # # # # # # # # # # #

# # # # UTILITIES # # # # 

## TODO make it smaller
def redraw_svg(context: 'Drawing_context', svg_path: 'Svg_path') -> Svg_drawing: 
    """ Create a new svg with layers (from context.svg_styles) and path 
    (from polylines) edited to fit scaled size and joined if cut """
    svg_size = context.svg_size
    factor = context.svg_factor
    drawing_styles = context.svg_styles
    css = f"@import url(../{BASE_CSS});"
    with Svg_drawing(svg_path.path, svg_size) as svg:
        svg.set_id(SVG_ID)
        style = svg.add_entity(Style, content = css) 
        layers = {}
        for drawing_style in context.svg_styles:
            layers[drawing_style] = svg.add_entity(Layer, label = drawing_style)
        for obj in svg_path.objects:
            for f in svg_path.objects[obj]:
                ## TODO use regex
                layer_label = f[-7:-4]
                layer = layers[layer_label]
                gr = layer.add_entity(Group)
                gr.set_id(f'{obj.name}_{layer_label}')
                for e in get_svg_groups(f, drawing_styles):

                    pl_coords = [transform_points(pl.attrib['points'], 
                        scale_factor=factor, rounding=ROUNDING) \
                                for pl in e.iter(PL_TAG)]

                    if layer.label == 'cut':
                        pl_coords = join_coords(pl_coords)

                    for coord in pl_coords:
                        path = gr.add_entity(Path, 
                                coords_string = get_path_coords(coord), 
                                coords_values = coord)
                        path.add_class(layer_label)
                        for collection in obj.collections:
                            path.add_class(collection)
                        path.set_attribute(SVG_ATTRIBUTES[layer.label]) 
    for obj in svg_path.objects:
        for f in svg_path.objects[obj]:
            os.remove(f)
    return svg


def get_svg_groups(svg_file: str, styles: list[str]) -> list[ET.Element]:
    """ Get all groups in svg_file with id in styles """
    svg_root = ET.parse(svg_file).getroot()
    groups = [g for g in svg_root.iter(G_TAG) if g.attrib['id'] in styles]
    return groups

def transform_points(pl_points: str, scale_factor: float = 1, 
        offset: float = 0, rounding = 16) -> list[tuple[float]]:
    """ Get pl_points from svg and return the edited coords 
        (scaled, moved and rounded) as list of tuple of float """
    coords = []
    coords_iter = re.finditer(r'([-\d\.]+),([-\d\.]+)', pl_points)
    for coord in coords_iter:
        x = round(float(coord.group(1)) * scale_factor, rounding)
        y = round(float(coord.group(2)) * scale_factor, rounding)
        coords.append((x, y))
    return coords

def get_path_coords(coords: list[tuple[float]]) -> str:
    """ Return the coords as string for paths """
    closed = coords[0] == coords[-1]
    string_coords = 'M '
    for co in coords[:-1]:
        string_coords += f'{str(co[0])},{str(co[1])} '
    closing = 'Z ' if closed else f'{str(coords[-1][0])},{str(coords[-1][1])} '
    string_coords += closing
    return string_coords

def get_polyline_coords(coords: list[tuple[float]]) -> str:
    """ Return the coords as string for polyline """
    string_coords = ''
    for co in coords:
        string_coords += f'{str(co[0])},{str(co[1])} '
    return string_coords

def join_coords(coords: list[tuple[float]]) -> list[list[tuple[float]]]:
    """ Join coords list (as from polyline) and put new coords lists in seqs """
    seqs = []
    for coord in coords:
        seqs = add_tail(seqs, coord)
    return seqs

def add_tail(sequences: list[list], tail: list) -> list[list[tuple[float]]]:
    """ Add tail to sequences and join it to every sequence 
        whith corresponding ends """
    to_del = []
    new_seq = tail
    last_joined = None
    seqs = [seq for seq in sequences for t in [0, -1]]
    for i, seq in enumerate(seqs):
        t = -(i%2) ## -> alternate 0 and -1
        ends = [seq[0], seq[-1]]
        if new_seq[t] not in ends or last_joined == seq:
            continue
        index = -ends.index(new_seq[t]) ## -> 0 | 1
        step = (-2 * index) - 1 ## -> -1 | 1
        val = 1 if t == 0 else -1 ## -> 1 | -1 | 1 | -1
        ## Cut first or last and reverse f necessary
        seq_to_check = new_seq[1+t:len(new_seq)+t][::step*val]
        ## Compose accordingly
        new_seq = [ii for i in [seq,seq_to_check][::step] for ii in i]
        last_joined = seq
        if seq not in to_del:
            to_del.append(seq)
    for s in to_del:
        sequences.remove(s)
    sequences.append(new_seq)
    return sequences
# # # # # # # # # # # # 

# # # # ARCHIVE # # # #
tuple_points = lambda x: [tuple([float(n) for n in i.split(',')]) 
        for i in x.split(' ')]
get_xml_elements = lambda container, element: list(
        container.iterdescendants(element))
get_pl_points = lambda polylines: [tuple_points(pt.attrib['points']) 
        for pt in polylines]
def get_rect_dimensions(rect) -> tuple[tuple[float], list[float]]: 
    """ Get position and dimensions of polyline rect in svg """
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
