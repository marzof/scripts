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
import xml.etree.ElementTree as ET
import re
from pathlib import Path as Filepath
from prj.drawing_context import Drawing_context
from prj.drawing_maker import Drawing_maker
from prj.drawing_subject import Drawing_subject
from prj.svg_path import svgs_data
from prj import svglib, BASE_CSS
from prj.svglib import Svg_drawing, Layer, Use, Style, prepare_obj_svg
import time

start_time = time.time()

print('\n\n\n###################################\n\n\n')


ARGS: list[str] = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]


drawings: list[Svg_drawing] = []
subjects: list[Drawing_subject] = []
drawing_times = {}

draw_context = Drawing_context(args = ARGS)
draw_maker = Drawing_maker(draw_context)

for subject in draw_context.subjects:
    print('Drawing', subject.name)
    drawing_start_time = time.time()
    draw_maker.draw(subject, draw_context.style)
    drawing_time = time.time() - drawing_start_time
    drawing_times[drawing_time] = subject.name
    print(f"   ...drawn in {drawing_time} seconds")
    subjects.append(subject)

for svg_data in svgs_data:
    drawing_data = svgs_data[svg_data]
    abstract_svg = prepare_obj_svg(draw_context, drawing_data)
    svg = abstract_svg.to_real(drawing_data.path)
    drawings.append(drawing_data.path)

print("\n--- Completed in %s seconds ---\n\n" % (time.time() - start_time))
for t in sorted(drawing_times):
    print(drawing_times[t], t)

## TODO clean up and complete here
def get_use_objects(filepath: Filepath) -> list[str]:
    svg_root = ET.parse(filepath).getroot()
    namespaces = dict([node for _, node in ET.iterparse(
        composition_filepath, events=['start-ns'])])
    xmlns_ns = f'{{{namespaces[""]}}}'
    xlink_ns = f'{{{namespaces["xlink"]}}}'
    use_tag = f'{xmlns_ns}use'
    use_objects = [element.attrib[f'{xlink_ns}title'] \
            for element in svg_root.iter() if element.tag == use_tag]
    return use_objects
def create_drawing_svg() -> None:
    with Svg_drawing(draw_context.drawing_camera.name + '.svg', 
            draw_context.svg_size) as composition:
        css = f"@import url({BASE_CSS});"
        style = composition.add_entity(Style, content = css) 
        for style in draw_context.svg_styles:
            layer = composition.add_entity(Layer, label = style)
            layer.set_id(style)
            for subject in subjects:
                use = layer.add_entity(Use, 
                    link = f'{subject.svg_path.path}#{subject.name}_{style}')
                use.set_id(f'{subject.name}_{style}')
                use.set_attribute({'xlink:title': subject.name})
                for collection in subject.collections:
                    use.add_class(collection)

def add_to_composition():
    pass

composition_filepath = Filepath(draw_context.drawing_camera.name + '.svg')
if not composition_filepath.is_file():
    create_drawing_svg()
else:
    use_objects = get_use_objects(composition_filepath)
    new_objects = [obj.name for obj in subjects if obj.name not in use_objects]
    if new_objects:
        add_to_composition()

create_drawing_svg() ## anyway


