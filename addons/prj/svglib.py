#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import os
import svgwrite
from svgwrite.extensions import Inkscape


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

    def add_entity(self, abs_entity: AbsSvg_entity,
            abs_container: 'AbsSvg_container' = None) -> None:
        if not abs_container:
            abs_container = self
        else:
            print('add to container', abs_container)
        if abs_entity not in abs_container.entities:
            abs_container.entities.append(abs_entity)

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
        AbsSvg_container.__init__(self)
        self.link = link
        self.tag = 'use'

    def add_entity(self, link: str) -> 'AbsUse':
        self.link = link
        return self

    def replace_content(self, link: str) -> 'AbsUse':
        self.link = link
        return self

    def to_real(self, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None) -> 'Use': 
        return Use(self.link, container, drawing)

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

    def replace_content(self, link: str) -> 'Use':
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

class AbsDefs(AbsSvg_container):
    def __init__(self):
        AbsSvg_container.__init__(self)
        self.tag = 'defs'

    def to_real(self, container: Svg_container = None, 
            drawing: 'Svg_drawing' = None) -> 'Defs': 
        return Defs(container, drawing)

class Defs(Svg_container):
    obj: svgwrite.container.Defs

    def __init__(self, container: Svg_container = None,
            drawing: 'Svg_drawing' = None):
        Svg_container.__init__(self)
        self.container = container
        Svg_entity.__init__(self, entity_type = 'defs', obj = drawing.obj.defs,
                container = container, drawing = drawing)

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
            self._get_tree_real(self, drawing, drawing)
        return drawing

    def _get_tree_real(self, abs_element: AbsSvg_entity, 
            container: Svg_container, drawing: 'Svg_drawing') -> None:
        """ Go deep in abs_element.entities and make content real """
        for e in abs_element.entities:
            real_e = e.to_real(drawing=drawing)
            real_e.obj.attribs.update(e.attributes)
            container.add_entity(real_e)
            if AbsSvg_container in e.__class__.__bases__:
                self._get_tree_real(e, real_e, drawing)

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

