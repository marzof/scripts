#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import xml.etree.ElementTree as ET
import prj.svglib as svglib
import re

NS_RE = re.compile(r'{(.*)}(.*)')

tags = {'svg': {'class': 'AbsSvg_drawing', 'get_data': lambda **data: []},
        'defs': {'class': 'AbsDefs', 'get_data': lambda **data: []},
        'g': {'class': 'AbsGroup', 'get_data': lambda **data: []},
        'style': {'class': 'AbsStyle', 
            'get_data': lambda **data: [i.text for i in data['element'].iter()]},
        'polyline': {'class': 'AbsPolyline', 
            'get_data': lambda **data: [get_polyline_points(data['element'])]},
        'use': {'class': 'AbsUse', 
            'get_data': lambda **data: [data['attribs']['xlink:href']]},
        }

param_dict = {
        'tag': lambda element, value: element.tag,
        'attrib_key': lambda element, key: key \
                if key in element.attributes else None,
        'attrib_value': lambda element, value: value \
                if value in element.attributes.values() else None,
        } 

def get_polyline_points(element:ET.Element) -> list[tuple[float]]:
    """ Return the points coords of element """
    points = []
    raw_points: list[str] = element.attrib['points'].split()
    for coords in raw_points:
        xy = []
        for co in coords.split(','):
            xy.append(float(co))
        points.append(tuple(xy))
    return points

# # # # CLASSES # # # #

class Svg_read:
    root: ET.Element
    namespaces: dict[str, str]
    tree: dict[tuple[int], ET.Element]

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.root = ET.parse(filepath).getroot()
        self.namespaces = dict([node for _, node in 
            ET.iterparse(filepath, events=['start-ns'])])
        self.ns_keys = [*self.namespaces.keys()]
        self.ns_values = [*self.namespaces.values()]
        self.tree = {}
        self._get_tree(self.root)
        self.drawing = self.tree[(0,)]

    def _get_tree(self, element: ET.Element, position: tuple[int] = (0,)) -> None:
        """ Populate element tree with abstract version of entities """
        abs_svg = self.get_abs_svg_class(element)
        self.tree.update({position: abs_svg})
        if len(position) > 1:
            parent = self.tree[position[:-1]]
            parent.add_entity(abs_svg)
        for i, child in enumerate(element):
            self._get_tree(child, position + (i,))

    def get_svg_elements(self, tag: str = None, attrib_key: str = None,
            attrib_value: str = None) -> list['svglib.AbsSvg_entity']:
        """ Get all elements of tree if they match with parameters """
        params = locals()
        params_to_check = {key: params[key] for key in params \
                if key != 'self' and params[key]}
        elements = []
        for element in self.tree.values():
            element_properties = [param_dict[key](element,params_to_check[key]) \
                    for key in params_to_check]
            if element_properties == [*params_to_check.values()]:
                elements.append(element)
        return elements

    def get_abs_svg_class(self, element: ET.Element) -> 'svglib.AbsSvg_entity':
        """ Return an abstract version of element """
        svg_ns = f'{{{self.namespaces[""]}}}'
        tag = element.tag[len(svg_ns):]
        attribs = {self.ns_to_attribs(k): v for k,v in element.attrib.items()}
        abs_class = tags[tag]['class']
        data = tags[tag]['get_data'](element = element, attribs = attribs)
        if tag == 'g' and 'inkscape:groupmode' in attribs:
            abs_class = 'AbsLayer'
            data = [attribs['inkscape:label']]
        svg_class_constructor = getattr(svglib, abs_class)
        abs_svg = svg_class_constructor(*data)
        abs_svg.set_attribute(attribs)
        return abs_svg

    def ns_to_attribs(self, attrib_key: str) -> dict[str, str]:
        """ Convert element attrib_key to corresponding namespace """
        new_attrib_key = attrib_key
        ns_in_attrib = NS_RE.match(attrib_key)
        if ns_in_attrib:
            idx = self.ns_values.index(ns_in_attrib.group(1))
            new_attrib_key = f'{self.ns_keys[idx]}:{ns_in_attrib.group(2)}'
        return new_attrib_key
