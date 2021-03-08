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

print('\n\n\n###################################\n\n\n')

import bpy
import sys, os
from prj import blend2svg
from prj import svg
import ast

norm_path = lambda x: os.path.realpath(x).replace(
        os.path.realpath('.'), '').strip(os.sep)

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]][0]
print('ARGS', ast.literal_eval('"' + ARGS + '"'))
#FLAGS = [arg for arg in ARGS if arg.startswith('-')]
RENDER_PATH = norm_path(bpy.context.scene.render.filepath)
FILE_PATH = bpy.path.abspath("//")

svg_data = blend2svg.get_svg(FILE_PATH + RENDER_PATH)
#for svg_file in svg_data['files']:
#    svg.set_data(svg_data['frame_size'])
#    svg.read_svg(svg_file, svg_data['frame_name'], svg_data['line_art_name'])
