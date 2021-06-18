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
#SVG_ATTRIBUTES = {'prj': {}, 'cut': {}, 'hid': {}, 'bak': {}}
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
    classes: str

    def __init__(self, entity_type: str, obj:svgwrite.base.BaseElement, 
            container: 'Svg_container', drawing: 'Svg_drawing'): 
        self.type: str = entity_type
        self.obj = obj
        self.classes = ''
        self.container = container
        self.drawing = drawing if drawing else container.drawing
        
    def set_id(self, entity_id: str):
        self.obj.__setitem__('id', entity_id)
        self.id: str = entity_id
        return self.id

    def add_class(self, entity_class: str):
        update_class = f'{self.classes} {entity_class}'.strip()
        self.obj.__setitem__('class', update_class)
        self.classes = update_class
        return self.classes

    def set_container(self, container:'Svg_container'):
        self.container = container

    def set_attribute(self, dic: dict[str, str]) -> None:
        self.obj.update(dic)

class Svg_container(Svg_entity):
    entities: dict[str,list[svgwrite.base.BaseElement]]

    def __init__(self):
        self.entities = {}

    def drawing_container(self, container: 'Svg_container') -> 'Svg_drawing':
        if isinstance(container, Svg_drawing):
            return container
        return self.drawing_container(container.container)

    def add_entity(self, class_type: type, **data) -> Svg_entity:
        if not isinstance(class_type, type):
            ## class_type can be an entity yet
            entity = class_type
            entity.set_container(self)
        else:
            entity = class_type(**data, container = self, drawing = self.drawing)
            if entity.type not in entity.container.entities:
                entity.container.entities[entity.type] = []
            entity.container.entities[entity.type].append(entity)
        self.obj.add(entity.obj)
        return entity

class Svg_graphics(Svg_entity):
    pass

class Use(Svg_container):
    obj: svgwrite.container.Use

    def __init__(self, link: str, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None):
        self.link = link
        Svg_entity.__init__(self, entity_type = 'use',
                obj = drawing.obj.use(href = link),
                container = container, drawing = drawing)

    def add_entity(self, link: str) -> 'Use':
        self.link = link
        return self

class Style(Svg_container):
    obj: svgwrite.container.Style

    def __init__(self, content: str, container: Svg_container = None,
            drawing: 'Svg_drawing' = None): 
        Svg_container.__init__(self)
        self.content = content if content else ''
        Svg_entity.__init__(self, entity_type = 'style',
                obj = drawing.obj.style(content),
                container = container, drawing = drawing)

        def add_entity(self, content: str) -> 'Style':
            self.content += content
            return self

        def replace_content(self, content: str) -> 'Style':
            self.content = content
            return self

class Group(Svg_container):
    obj: svgwrite.container.Group

    def __init__(self, container: Svg_container = None,
            drawing: 'Svg_drawing' = None):
        Svg_container.__init__(self)
        self.container = container
        Svg_entity.__init__(self, entity_type = 'group', obj = drawing.obj.g(),
                container = container, drawing = drawing)

class Layer(Svg_container):
    obj: svgwrite.container.Group

    def __init__(self, label: str, container: Svg_container = None,
            drawing: 'Svg_drawing' = None):
        Svg_container.__init__(self)
        self.label = label
        Svg_entity.__init__(self, entity_type = 'layer',
                obj = Inkscape(drawing.obj).layer(label=label),
                container = container, drawing = drawing)

class Polyline(Svg_graphics):
    obj: svgwrite.shapes.Polyline

    def __init__(self, points: list[tuple[float]], 
            container: Svg_container = None, drawing: 'Svg_drawing' = None): 
        self.points = points
        Svg_entity.__init__(self, entity_type = 'polyline',
                obj = drawing.obj.polyline(points = self.points),
                container = container, drawing = drawing)

class Path(Svg_graphics):
    obj: svgwrite.path.Path

    def __init__(self, coords_string: str, coords_values: list[tuple[float]],
            container: Svg_container = None, drawing: 'Svg_drawing' = None): 
        self.points = coords_values
        Svg_entity.__init__(self, entity_type = 'path',
                obj = drawing.obj.path(coords_string), 
                container = container, drawing = drawing)

class Svg_drawing(Svg_container):
    obj: svgwrite.drawing.Drawing
    filepath: str 
    size: tuple[str]

    def __init__(self, filepath: str, size = ('100mm', '100mm')):
        Svg_container.__init__(self)
        self.filepath = filepath
        self.size = size
        self.drawing = self
        self.container = self

    def __enter__(self) -> 'Svg_drawing':
        self.obj = svgwrite.drawing.Drawing(filename= self.filepath, 
                size=self.size)
        Svg_entity.__init__(self, entity_type = 'drawing', obj = self.obj,
                container = self.container, drawing = self.drawing)
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.obj.save(pretty=True)
# # # # # # # # # # # #

# # # # UTILITIES # # # # 

def collect_and_fit_svg(context: 'Drawing_context', svg_path: 'Svg_path') \
        -> Svg_drawing: 
    """ Collect drawing styles and object parts in a new svg,
        scale entities to fit drawing size and join cut pahts """

    css = f"@import url(../{BASE_CSS});"
    files = {f['path']: {'obj':obj, 'data':f['data']} 
            for obj in svg_path.objects for f in svg_path.objects[obj]}

    with Svg_drawing(svg_path.path, context.svg_size) as svg:
        svg.set_id(SVG_ID)
        style = svg.add_entity(Style, content = css) 

        layers = {}
        for drawing_style in context.svg_styles:
            layer = Layer(label = drawing_style, drawing = svg)
            layers[drawing_style] = layer
            svg.add_entity(layer)

        for f in files:
            obj = files[f]['obj']
            layer_label = files[f]['data']
            layer = layers[layer_label]
            g = Group(drawing = svg)
            layer.add_entity(g)
            g.set_id(f'{obj.name}_{layer.label}')

            is_cut = layer.label == 'cut'
            paths = paths_from_file(f, svg, context.svg_factor, obj, 
                    layer.label, is_cut)
            for path in paths:
                g.add_entity(path)

    for f in files:
        os.remove(f)
    return svg

def paths_from_file(f: str, svg:Svg_drawing, factor: float, 
        obj:'Drawing_subject', layer_label: str, join: bool) -> list[Path]:
    """ Extract paths from file f after applying factor and assign classes """
    coords = []
    paths = []
    xml_groups = get_svg_groups(f, [layer_label])
    for element in xml_groups:
        pl_coords = get_svg_coords(element, factor, join)

        for coord in pl_coords:
            path = Path(coords_string = get_path_coords(coord), 
                    coords_values = coord, drawing = svg)
            path.add_class(layer_label)
            for collection in obj.collections:
                path.add_class(collection)
            paths.append(path)
    return paths

def get_svg_coords(element: 'xml.etree.ElementTree.Element', 
        factor: float, join: bool) -> list[list[tuple[float]]]:
    """ Extract (and join if needed) coords from element and apply a 
        transformation by factor """
    pl_points = [pl.attrib['points'] for pl in element.iter(PL_TAG)]
    pl_coords = [transform_points(points, scale_factor=factor, 
        rounding=ROUNDING) for points in pl_points]
    if join:
        return join_coords(pl_coords)
    return pl_coords

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

def add_tail(sequences: list[list[tuple[float]]], tail: list[tuple[float]]) -> \
        list[list[tuple[float]]]:
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

