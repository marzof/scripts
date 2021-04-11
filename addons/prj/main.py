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
ROUNDING: int = 4

drawings: list[Svg_drawing] = []
svg_files: str = []

def draw_subject(subject: 'bpy.types.Object', context: Drawing_context): 
    """ Draw subject in svg and return its filepath """
    print('Subject:', subject.name)
    draw_subj = Drawing_subject(subject, context)
    if draw_subj.visible:
        print(subject.name, 'is visible')
        return draw_maker.draw(draw_subj, context.style)

def pl_to_path_points(pl_points: str, scale_factor: float = 1, 
        offset: float = 0, rounding = 16) -> str:
    coords = 'M '
    coords_iter = re.finditer(r'[\d\.]+', pl_points)
    for i, coord in enumerate(coords_iter, 1):
        separator = ',' if i % 2 else ' '
        co = round(float(coord.group()) * scale_factor, rounding)
        coords += str(co) + separator
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

for svg_file in svg_files:
    svg_root = ET.parse(svg_file).getroot()
    groups = [g for g in svg_root.iter(g_tag) if g.attrib['id'] in styles]
    with Svg_drawing(svg_file, svg_size) as svg:
        for group in groups:
            layer_label = group.attrib['id']
            layer = svg.add_entity(Layer, layer_label) 
            for pl in group.iter(pl_tag):
                coords = pl_to_path_points(pl.attrib['points'], 
                        scale_factor=factor, rounding=ROUNDING)
                path = layer.add_entity(Path, coords)
                path.set_attribute(SVG_ATTRIBUTES[layer.label]) 

        #frame_name = prj.SVG_GROUP_PREFIX + draw_context.FRAME_NAME
        #frame = svg_draw.svg.find_id(frame_name) 
        #    ## svg_draw.svg = svgutils.compose.SVG(filepath)
        #    ## replacing self.original_svg  
        #base_offset, base_size = prj_utils.get_rect_dimensions(frame)
        #    ## move prj_svglib.get_rect_dimensions() to prj_utils
        #base_ratio = draw_context.frame_size / base_size[0]
        #px_to_mm_factor = 10 * base_ratio
        #unit_to_px_factor = RESOLUTION_FACTOR * base_ratio
        #px2mm = lambda x: self.px_to_mm_factor * x

        ## scaled_svg = Svg_drawing(filepath=svg_path)
        ## prepare entities, layers and add to scaled_svg

        #svg = Svg_drawing(filepath=svg_path, context= draw_context, 
        #        subject=subj.name)
#        drawings.append(svg_to)
