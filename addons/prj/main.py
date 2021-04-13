#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

# Copyright (c) 2021 Marco Ferrara

# License:
# GNU GPL License
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Dependencies: 
# TODO...


import sys
import numpy
import prj
import re
from prj.prj_drawing_classes import Drawing_context, Draw_maker, Drawing_subject
from prj.prj_svglib import Svg_drawing, Layer, Path, Polyline, SVG_ATTRIBUTES
from prj import prj_utils
from prj import prj_svglib
import xml.etree.ElementTree as ET

print('\n\n\n###################################\n\n\n')

format_svg_size = lambda x, y: (str(x) + 'mm', str(x) + 'mm')

ARGS: list[str] = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch
ROUNDING: int = 3

drawings: list[Svg_drawing] = []
svg_files: str = []

def draw_subject(subject: 'bpy.types.Object', context: Drawing_context): 
    """ Draw subject in svg and return its filepath """
    print('Subject:', subject.name)
    draw_subj = Drawing_subject(subject, context)
    if draw_subj.visible:
        print(subject.name, 'is visible')
        return draw_maker.draw(draw_subj, context.style)

def format_points(pl_points: str, scale_factor: float = 1, 
        offset: float = 0, rounding = 16) -> dict:
    """ Get pl_points from svg and return the edited coords 
    (scaled, moved and rounded) as both string and list of tuple of float """
    coords = {'path_string': 'M ', 'polyline_string': '', 'values': []}
    coords_iter = re.finditer(r'([\d\.]+),([\d\.]+)', pl_points)
    for i, coord in enumerate(coords_iter, 1):
        x = round(float(coord.group(1)) * scale_factor, rounding)
        y = round(float(coord.group(2)) * scale_factor, rounding)
        string = f'{str(x)},{str(y)} '
        coords['path_string'] += string
        coords['polyline_string'] += string
        coords['values'].append((x, y))
    return coords


draw_context = Drawing_context(args = ARGS)

## TODO Clean up 
svg_size = format_svg_size(draw_context.frame_size * 10, 
        draw_context.frame_size * 10)
factor = draw_context.frame_size/draw_context.RENDER_RESOLUTION_X * \
        RESOLUTION_FACTOR
pl_tag = '{http://www.w3.org/2000/svg}polyline'
g_tag = '{http://www.w3.org/2000/svg}g'
styles = [prj.STYLES[d_style]['name'] for d_style in draw_context.style]
# # # # # 

draw_maker = Draw_maker(draw_context)

for subject in draw_context.subjects:
    drawing = draw_subject(subject, draw_context)
    svg_files.append(drawing)

#svg_files = ['/home/mf/Documents/TODO/svg_composition/graph/Cube.svg']
for svg_file in svg_files:
    svg_root = ET.parse(svg_file).getroot()
    groups = [g for g in svg_root.iter(g_tag) if g.attrib['id'] in styles]
    with Svg_drawing(svg_file, svg_size) as svg:
        for g in groups:
            layer_label = g.attrib['id']
            layer = svg.add_entity(Layer, label = layer_label) 
            ## TODO put order here and fix handling of multiple cut 
            points = {}
            seq = []
            coords_list = []
            for i, pl in enumerate(g.iter(pl_tag)):
                coords = format_points(pl.attrib['points'], 
                        scale_factor=factor, rounding=ROUNDING)
                coords_list.append(coords)
                if layer.label == 'cut':
                    #print('pl #', i, coords['values'])
                    #print('points', points)
                    if coords['values'][0] not in points:
                        points[(coords['values'][0])] = []
                    elif not seq:
                        seq.append(points[coords['values'][0]][0])
                        seq.append(i)
                    else:
                        #print('else first', i, points[coords['values'][0]])
                        if seq[-1] == points[coords['values'][0]][0]:
                            seq.append(i)
                    points[(coords['values'][0])].append(i)
                    #print('seq first', seq)
                    #print('points', points)
                    if coords['values'][-1] not in points:
                        points[(coords['values'][-1])] = []
                    elif not seq:
                        seq.append(points[coords['values'][-1]][0])
                        seq.append(i)
                    else:
                        #print('else last', i, points[coords['values'][-1]])
                        if seq[-1] == i:
                            seq.append(points[coords['values'][-1]][0])
                    points[(coords['values'][-1])].append(i)
                    #print('seq last', seq)
                    #print('points', points)
                path = layer.add_entity(Path, 
                        coords_string = coords['path_string'], 
                        coords_values = coords['values'])
                print(coords['path_string'])
                path.set_attribute(SVG_ATTRIBUTES[layer.label]) 
            #print('points', points)
            joined_path = 'M '
            joined_path_values = []
            for i in seq[:-1]:
                #print(coords_list[i]['path_string'])
                co = coords_list[i]['values'][1:]
                joined_path += (' '.join([f'{c[0]},{c[1]}' for c in co])) + ' '
                joined_path_values += co
            print(joined_path_values)
            print(joined_path)
            if layer.label == 'cut':
                path = layer.add_entity(Path, 
                        coords_string = joined_path,
                        coords_values = joined_path_values)
            # # # # # # # # # # # # # #
        #prj_svglib.join_paths(layer)

    #drawings.append(svg_to)
