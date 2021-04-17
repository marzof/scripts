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
import itertools
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

def draw_subject(subject: 'bpy.types.Object', context: Drawing_context) -> str: 
    """ Draw subject in svg and return its filepath """
    print('Subject:', subject.name)
    draw_subj = Drawing_subject(subject, context)
    if draw_subj.visible:
        print(subject.name, 'is visible')
        return draw_maker.draw(draw_subj, context.style)

def transform_points(pl_points: str, scale_factor: float = 1, 
        offset: float = 0, rounding = 16) -> list[tuple[float]]:
    """ Get pl_points from svg and return the edited coords 
        (scaled, moved and rounded) as list of tuple of float """
    coords = []
    coords_iter = re.finditer(r'([\d\.]+),([\d\.]+)', pl_points)
    for coord in coords_iter:
        x = round(float(coord.group(1)) * scale_factor, rounding)
        y = round(float(coord.group(2)) * scale_factor, rounding)
        coords.append((x, y))
    return coords

def get_path_coords(coords: list[tuple[float]]) -> str:
    """ Return the coords as string for paths """
    string_coords = 'M '
    for co in coords:
        string_coords += f'{str(co[0])},{str(co[1])} '
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

draw_context = Drawing_context(args = ARGS)

svg_size = format_svg_size(draw_context.frame_size * 10, 
        draw_context.frame_size * 10)
factor = draw_context.frame_size/draw_context.RENDER_RESOLUTION_X * \
        RESOLUTION_FACTOR
pl_tag = '{http://www.w3.org/2000/svg}polyline'
g_tag = '{http://www.w3.org/2000/svg}g'
styles = [prj.STYLES[d_style]['name'] for d_style in draw_context.style]

draw_maker = Draw_maker(draw_context)

for subject in draw_context.subjects:
    drawing = draw_subject(subject, draw_context)
    svg_files.append(drawing)

for svg_file in svg_files:
    svg_root = ET.parse(svg_file).getroot()
    groups = [g for g in svg_root.iter(g_tag) if g.attrib['id'] in styles]
    with Svg_drawing(svg_file, svg_size) as svg:
        for g in groups:
            layer_label = g.attrib['id']
            layer = svg.add_entity(Layer, label = layer_label) 

            coords = [transform_points(pl.attrib['points'], scale_factor=factor, 
                rounding=ROUNDING) for pl in g.iter(pl_tag)]

            if layer.label == 'cut':
                coords = join_coords(coords)

            for coord in coords:
                path = layer.add_entity(Path, 
                        coords_string = get_path_coords(coord), 
                        coords_values = coord)
                path.set_attribute(SVG_ATTRIBUTES[layer.label]) 

        drawings.append(svg)
