#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import re
import os
import numpy as np
import math
import svgwrite
from svgwrite.extensions import Inkscape
import xml.etree.ElementTree as ET
from prj import BASE_CSS, SVG_ID, ROUNDING
from prj.svgread import Svg_read


POLYLINE_TAG: str = 'polyline'
PL_TAG = '{http://www.w3.org/2000/svg}polyline'
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

class AbsSvg_entity: 
    attributes: dict[str,str]

    def __init__(self):
        self.attributes = {}

    def set_attribute(self, dic: dict[str, str]) -> None:
        self.attributes.update(dic)

    def add_class(self, entity_class: str) -> None:
        self.set_attribute({'class': entity_class})

    def set_id(self, entity_id: str) -> None:
        self.set_attribute({'id': entity_id})

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

class AbsSvg_container(AbsSvg_entity):
    entities: list[AbsSvg_entity]

    def __init__(self):
        AbsSvg_entity.__init__(self)
        self.entities = []

    def add_entity(self, abs_entity: AbsSvg_entity) -> None:
        if abs_entity not in self.entities:
            self.entities.append(abs_entity)

class Svg_container(Svg_entity):
    entities: dict[str,list[Svg_entity]]

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

class AbsUse(AbsSvg_container):
    def __init__(self, link: str):
        self.link = link
        self.tag = 'use'

    def add_entity(self, link: str) -> 'Use':
        self.link = link
        return self

    def replace_content(self, link: str) -> 'Use':
        self.link = link
        return self

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

class AbsStyle(AbsSvg_container):
    def __init__(self, content: str):
        AbsSvg_container.__init__(self)
        self.content = content
        self.tag = 'style'

    def add_entity(self, content: str) -> 'Style':
        self.content += content
        return self

    def replace_content(self, content: str) -> 'Style':
        self.content = content
        return self

    def to_real(self, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None) -> 'Style': 
        return Style(self.content, container, drawing)

class Style(Svg_container):
    obj:svgwrite.container.Style

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

class AbsGroup(AbsSvg_container):
    def __init__(self):
        AbsSvg_container.__init__(self)
        self.tag = 'g'

    def to_real(self, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None) -> 'Group': 
        return Group(container, drawing)

class Group(Svg_container):
    obj: svgwrite.container.Group

    def __init__(self, container: Svg_container = None,
            drawing: 'Svg_drawing' = None):
        Svg_container.__init__(self)
        self.container = container
        Svg_entity.__init__(self, entity_type = 'group', obj = drawing.obj.g(),
                container = container, drawing = drawing)

class AbsLayer(AbsSvg_container):
    def __init__(self, label: str):
        AbsSvg_container.__init__(self)
        self.tag = 'g'
        self.label = label

    def to_real(self, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None) -> 'Layer': 
        return Layer(self.label, container, drawing)

class Layer(Svg_container):
    obj: svgwrite.container.Group

    def __init__(self, label: str, container: Svg_container = None,
            drawing: 'Svg_drawing' = None):
        Svg_container.__init__(self)
        self.label = label
        Svg_entity.__init__(self, entity_type = 'layer',
                obj = Inkscape(drawing.obj).layer(label=label),
                container = container, drawing = drawing)

class AbsPolyline(AbsSvg_entity):
    def __init__(self, points: list[tuple[float]]):
        AbsSvg_entity.__init__(self)
        self.points = points
        self.tag = 'polyline'
 
    def to_real(self, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None) -> 'Polyline': 
        return Polyline(self.points, container, drawing)

class Polyline(Svg_graphics):
    obj: svgwrite.shapes.Polyline

    def __init__(self, points: list[tuple[float]], 
            container: Svg_container = None, drawing: 'Svg_drawing' = None): 
        self.points = points
        Svg_entity.__init__(self, entity_type = 'polyline',
                obj = drawing.obj.polyline(points = self.points),
                container = container, drawing = drawing)

class AbsPath(AbsSvg_entity):
    def __init__(self, coords_string: str, coords_values: list[tuple[float]]):
        AbsSvg_entity.__init__(self)
        self.string_points = coords_string
        self.points = coords_values
        self.tag = 'path'

    def to_real(self, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None) -> 'Path': 
        return Path(self.string_points, self.points, container, drawing)

class Path(Svg_graphics):
    obj: svgwrite.path.Path

    def __init__(self, coords_string: str, coords_values: list[tuple[float]],
            container: Svg_container = None, drawing: 'Svg_drawing' = None): 
        self.string_points = coords_string
        self.points = coords_values
        Svg_entity.__init__(self, entity_type = 'path',
                obj = drawing.obj.path(coords_string), 
                container = container, drawing = drawing)

class AbsSvg_drawing(AbsSvg_container):
    def __init__(self, size: tuple[str] = ('100mm', '100mm')):
        AbsSvg_container.__init__(self)
        self.size = size
        self.tag = 'svg'

    def to_real(self, filepath: str) -> 'Svg_drawing': 
        """ Create a new Svg_drawing and make real all included elements """
        with Svg_drawing(filepath, self.size) as drawing:
            drawing.obj.attribs.update(self.attributes)
            self._get_tree(self, drawing, drawing)
        return drawing

    def _get_tree(self, abs_element: AbsSvg_entity, container: Svg_container, 
            drawing: 'Svg_drawing') -> None:
        """ Go deep in abs_element.entities and make content real """
        for e in abs_element.entities:
            real_e = e.to_real(drawing=drawing)
            real_e.obj.attribs.update(e.attributes)
            container.add_entity(real_e)
            if AbsSvg_container in e.__class__.__bases__:
                self._get_tree(e, real_e, drawing)

class Svg_drawing(Svg_container):
    obj: svgwrite.drawing.Drawing
    filepath: str 
    size: tuple[str]

    def __init__(self, filepath: str, size: tuple[str] = ('100mm', '100mm')):
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

def prepare_obj_svg(context: 'Drawing_context', svg_path: 'Svg_path') \
        -> AbsSvg_drawing:
    """ Create an abstract version of object svg """

    files = {f['path']: {'obj':obj, 'data':f['data']} 
            for obj in svg_path.objects for f in svg_path.objects[obj]}
    css = f"@import url(../{BASE_CSS});"
    abssvg = AbsSvg_drawing(context.svg_size)
    abssvg.set_id(SVG_ID)
    absstyle = AbsStyle(content = css) 
    abssvg.add_entity(absstyle)

    abslayers = {}
    for drawing_style in context.svg_styles:
        abslayer = AbsLayer(label = drawing_style)
        abslayers[drawing_style] = abslayer
        abssvg.add_entity(abslayer)

    for f in files:
        obj = files[f]['obj']
        layer_label = files[f]['data']
        abslayer = abslayers[layer_label]
        absgroup = AbsGroup()
        absgroup.set_id(f'{obj.name}_{abslayer.label}')
        abslayer.add_entity(absgroup)
        is_cut = abslayer.label == 'cut'

        svg_read = Svg_read(f)
        abspaths = []
        all_points = []
        abspolylines = svg_read.get_svg_elements('polyline')
        for pl in abspolylines:
            pl.points = transform_points(pl.points, context.svg_factor, ROUNDING)
            all_points.append(pl.points[:])

        if is_cut:
            joined_points = join_coords(all_points)
            for coords in joined_points:
                abspath = AbsPath(coords_string = get_path_coords(coords), 
                        coords_values = coords)
                abspaths.append(abspath)
        else:
            for pl in abspolylines:
                abspath = AbsPath(coords_string = get_path_coords(pl.points),
                        coords_values = pl.points)
                abspaths.append(abspath) 

        for abspath in abspaths:
            abspath.add_class(layer_label)
            for collection in obj.collections:
                abspath.add_class(collection)
            absgroup.add_entity(abspath)

    #if 'cut' in context.svg_styles:
    #    clip_cut(layers['prj'], layers['cut'])

    #for f in files:
    #    os.remove(f)

    return abssvg

## TODO develop this
def clip_cut(prj_layer, cut_layer):
    #clipper = Clipper()
    prj_points, cut_points = [], []

    prj_entities = list(prj_layer.entities.values())[0][0].entities
    for entity in prj_entities:
        if entity == 'path':
            for path in prj_entities[entity]:
                prj_points.append(path.points)

    cut_entities = list(cut_layer.entities.values())[0][0].entities
    for entity in cut_entities:
        if entity == 'path':
            for path in cut_entities[entity]:
                cut_points.append(path.points)

    #new_prj_points = clipper.clip(cut_points, prj_points)

def transform_points(points:list[tuple[float]], factor: float = 1, 
        rounding: int = 16) -> list[tuple[float]]:
    """ Scale and round points """ 
    new_points = []
    for coords in points:
        new_coord = tuple([round(co*factor, rounding) for co in coords])
        new_points.append(new_coord)
    return new_points

def get_path_coords(coords: list[tuple[float]]) -> str:
    """ Return the coords as string for paths """
    closed = coords[0] == coords[-1]
    string_coords = 'M '
    for co in coords[:-1]:
        string_coords += f'{str(co[0])},{str(co[1])} '
    closing = 'Z ' if closed else f'{str(coords[-1][0])},{str(coords[-1][1])} '
    string_coords += closing
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

