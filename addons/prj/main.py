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
import prj
from prj import prj_svglib
from prj.prj_drawing_classes import Drawing_context, Draw_maker, Drawing_subject
from prj.prj_svglib import Svg_drawing, Layer, Path, Use, SVG_ATTRIBUTES, PL_TAG

print('\n\n\n###################################\n\n\n')


ARGS: list[str] = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
ROUNDING: int = 3
SVG_ID = 'svg'
svg_suffix = '.edit.svg'
svg_suffix = ''

def draw_subject(subject: 'bpy.types.Object', context: Drawing_context) -> str: 
    """ Draw subject in svg and return its filepath """
    print('Subject:', subject.name)
    draw_subj = Drawing_subject(subject, context)
    if draw_subj.visible:
        print(subject.name, 'is visible')
        drawing = draw_maker.draw(draw_subj, context.style)
        return drawing

def redraw_svg(svg_file:str, svg_size: tuple[str], factor: float,
        styles: list[str]) -> Svg_drawing:
    """ Create a new svg with layers (from groups) and path (from polylines)
        edited to fit scaled size and joined if cut """
    groups = prj_svglib.get_svg_groups(svg_file, styles)
    with Svg_drawing(svg_file + svg_suffix, svg_size) as svg:
        svg.set_id(SVG_ID)
        for g in groups:
            layer_label = g.attrib['id']
            layer = svg.add_entity(Layer, label = layer_label) 
            layer.set_id(layer_label)

            pl_coords = [prj_svglib.transform_points(pl.attrib['points'], 
                scale_factor=factor, rounding=ROUNDING) for pl in g.iter(PL_TAG)]

            if layer.label == 'cut':
                pl_coords = prj_svglib.join_coords(pl_coords)

            for coord in pl_coords:
                path = layer.add_entity(Path, 
                        coords_string = prj_svglib.get_path_coords(coord), 
                        coords_values = coord)
                path.set_attribute(SVG_ATTRIBUTES[layer.label]) 
    return svg

drawings: list[Svg_drawing] = []
svg_files: str = []

draw_context = Drawing_context(args = ARGS)
draw_maker = Draw_maker(draw_context)

for subject in draw_context.subjects:
    drawing = draw_subject(subject, draw_context)
    svg_files.append(drawing)

for svg_file in svg_files:
    svg = redraw_svg(svg_file, draw_context.svg_size, 
            draw_context.svg_factor, draw_context.svg_styles)
    drawings.append(svg)

with Svg_drawing('composition.svg', draw_context.svg_size) as composition:
    for style in draw_context.svg_styles:
        layer = composition.add_entity(Layer, label = style)
        for svg_file in svg_files:
            layer.add_entity(Use, link = f'{svg_file}{svg_suffix}#{style}')

