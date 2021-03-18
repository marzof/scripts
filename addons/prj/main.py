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
from prj.prj_drawing_classes import Drawing_context, Draw_maker, Drawing_subject
from prj.prj_svglib import Svg_drawing

print('\n\n\n###################################\n\n\n')

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]

drawings: list[Svg_drawing] = []

draw_context = Drawing_context(args = ARGS)
draw_maker = Draw_maker(draw_context)
for subj in draw_context.subjects:
    print('Subject:', subj.name)
    draw_subj = Drawing_subject(subj, draw_maker)
    for style in draw_context.style:
        print('style:', style)
        drawing = draw_maker.draw(draw_subj, style)
        svg = Svg_drawing(drawing, draw_context, subj.name)
        drawings.append(svg)
