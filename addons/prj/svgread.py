#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import xml.etree.ElementTree as ET
import prj.svglib as svglib

tags = {'svg': {'abs_class': 'AbsSvg_drawing', 'data':[]},
        'g': {'abs_class': 'AbsGroup', 'data':[]},
        'polyline': {'abs_class': 'AbsPolyline', 'data':[]},
        }

def get_polyline_points(element:ET.Element) -> list[tuple[float]]:
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
        self.tree = {}
        self._get_tree(self.root)

    def _get_tree(self, element: ET.Element, position: tuple[int] = (0,)) -> None:
        """ Populate element tree of abstract version of entities """
        abs_svg = self._get_abs_svg_class(element)
        self.tree.update({position: abs_svg})
        for i, child in enumerate(element):
            self._get_tree(child, position + (i,))

    def get_svg_elements(self, tag: str) -> list['svglib.AbsSvg_entity']:
        """ Get all elements of tree with tag """
        element_tag = tag
        elements = [el for el in self.tree.values() if el.tag == element_tag]
        return elements

    def _get_abs_svg_class(self, element: ET.Element) -> 'svglib.AbsSvg_entity':
        """ Return an abstract version of element """
        ns = f'{{{self.namespaces[""]}}}'
        tag = element.tag[len(ns):]
        abs_class = tags[tag]['abs_class']
        data = tags[tag]['data']
        if tag == 'polyline':
            data = [get_polyline_points(element)]
        abs_svg = getattr(svglib, abs_class)(*data)
        abs_svg.set_attribute(element.attrib)
        return abs_svg
