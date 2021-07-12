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

import bpy
import sys
import prj
from pathlib import Path as Filepath
from prj.svg_path import svgs_data
from prj.svgread import Svg_read
from prj.svg_handling import prepare_composition, prepare_obj_svg
from prj.svg_handling import filter_subjects_for_svg, add_subjects_as_use
from prj.drawing_context import Drawing_context, is_renderables
from prj.drawing_maker import Drawing_maker
from prj.drawing_subject import libraries
import time

drawings: list['Svg_drawing'] = []
subjects: list['Drawing_subject'] = []

def draw_subjects(draw_context: 'Drawing_context', draw_maker: 'Drawing_maker',
        timing_test: bool = False) -> None:
    """ Get exported svgs for every subject (or parts of it) for every style """
    drawing_times: dict[float, str] = {}
    print('Prepare drawings')
    prepare_start_time = time.time()

    cutter = draw_context.cutter
    cutter.obj.hide_viewport = False

    bpy.context.window.scene = draw_context.working_scene

    for subject in draw_context.subjects:
        subject.get_bounding_rect()
        subject.get_overlap_subjects(subjects)

    if timing_test:
        for subject in draw_context.subjects:
            subject.obj.hide_viewport = True
    print(f'\t...completed in {(time.time() - prepare_start_time)}\n')

    ## TODO check time increase due to cutter
    ## Draw every subject
    for subject in draw_context.subjects:
        print('Drawing', subject.name)
        hidden_subjects = []
        drawing_start_time = time.time()
        subject.obj.hide_viewport = False
        for other_subj in draw_context.subjects:
            if other_subj not in subject.overlapping_subjects + [subjects, cutter]:
                hidden_subjects.append(other_subj)
                other_subj.obj.hide_viewport = True
        draw_maker.draw(subject, draw_context.style, cutter)
        drawing_time = time.time() - drawing_start_time
        drawing_times[drawing_time] = subject.name
        subjects.append(subject)
        subject.obj.hide_viewport = timing_test
        for other_subj in hidden_subjects:
            other_subj.obj.hide_viewport = False
        print(f"\t...drawn in {drawing_time} seconds")

    ## Restore objects visibility
    if timing_test:
        print('Restore objects visibility')
        restore_start_time = time.time()
        for subject in draw_context.subjects:
            if not subject.library:
                subject.obj.hide_viewport = False
        print(f'\t...completed in {(time.time() - restore_start_time)}\n')

    print('\n')
    for t in sorted(drawing_times):
        print(drawing_times[t], t)
    print(f'Drawn objects in {sum(drawing_times.keys())} seconds\n')
    return 

def rewrite_svgs(draw_context: 'Drawing_context') -> None:
    """ Get a single and organized svg for every subject """
    print('Start rewriting svg')
    rewrite_svgs_start_time = time.time()
    for svg_data in svgs_data:
        drawing_data = svgs_data[svg_data]
        abstract_subj_svg = prepare_obj_svg(draw_context, drawing_data)
        subj_svg = abstract_subj_svg.to_real(drawing_data.path)
        drawings.append(drawing_data.path)
    print(f'\t...completed in {(time.time() - rewrite_svgs_start_time)}\n')

def get_svg_composition(draw_context: 'Drawing_context') -> None:
    """ Collect every subject svg in a single composed svg 
        or add new subject to existing composed svg """
    ## TODO check why a lot of defs elements are created
    print('Start composition')
    composition_start_time = time.time()
    composition_filepath = Filepath(draw_context.drawing_camera.path + '.svg')
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
    print(f'\t...completed in {(time.time() - composition_start_time)}\n')


def main() -> None:
    start_time = time.time()
    context = bpy.context
    args = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
    draw_context = Drawing_context(args, context)
    draw_maker = Drawing_maker(draw_context)
    draw_subjects(draw_context, draw_maker)
    rewrite_svgs(draw_context)
    get_svg_composition(draw_context)
    print("\n--- Completed in %s seconds ---\n\n" % (time.time() - start_time))

if __name__ == "__main__":
    main()
