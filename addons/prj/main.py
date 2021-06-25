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
from pathlib import Path as Filepath
from prj.drawing_context import Drawing_context
from prj.drawing_maker import Drawing_maker
from prj.svg_path import svgs_data
from prj.svgread import Svg_read
from prj.svg_handling import prepare_composition, prepare_obj_svg
from prj.svg_handling import filter_subjects_for_svg, add_subjects_as_use
import time

start_time = time.time()

print('\n\n\n###################################\n\n\n')


ARGS: list[str] = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]


drawings: list['Svg_drawing'] = []
subjects: list['Drawing_subject'] = []
drawing_times = {}

draw_context = Drawing_context(args = ARGS)
draw_maker = Drawing_maker(draw_context)

## Get exported svgs for every subject (or parts of it) for every style
for subject in draw_context.subjects:
    print('Drawing', subject.name)
    drawing_start_time = time.time()
    draw_maker.draw(subject, draw_context.style)
    drawing_time = time.time() - drawing_start_time
    drawing_times[drawing_time] = subject.name
    print(f"   ...drawn in {drawing_time} seconds")
    subjects.append(subject)

## Get a single and organized svg for every subject
for svg_data in svgs_data:
    drawing_data = svgs_data[svg_data]
    abstract_subj_svg = prepare_obj_svg(draw_context, drawing_data)
    subj_svg = abstract_subj_svg.to_real(drawing_data.path)
    drawings.append(drawing_data.path)

## Collect every subject svg in a single composed svg 
## or add new subject to existing composed svg
composition_filepath = Filepath(draw_context.drawing_camera.name + '.svg')
if not composition_filepath.is_file():
#if False:
    abstract_composition = prepare_composition(draw_context, subjects)
else:
    existing_composition = Svg_read(composition_filepath)
    new_subjects = filter_subjects_for_svg(existing_composition, subjects)
    #new_subjects = subjects
    if new_subjects:
        for style in draw_context.svg_styles:
            container = existing_composition.get_svg_elements('g', 
                    'inkscape:label', style)[0]
            add_subjects_as_use(new_subjects, style, container)
    abstract_composition = existing_composition.drawing
composition = abstract_composition.to_real(composition_filepath)

print("\n--- Completed in %s seconds ---\n\n" % (time.time() - start_time))
for t in sorted(drawing_times):
    print(drawing_times[t], t)
