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
import time

drawings: list['Svg_drawing'] = []
subjects: list['Drawing_subject'] = []

def hide_objects(objs_to_hide: list[bpy.types.Object], 
        objs_to_show: list[bpy.types.Object], hide_anyway: bool) \
                -> dict[bpy.types.Object, bool]:
    """ Hide objs_to_hide except objs_to_show (if not hide_anyway) """
    object_visibility = {}
    objects_to_hide = [obj for obj in objs_to_hide if obj not in objs_to_show]
    objects = (objs_to_show * hide_anyway) + objects_to_hide
    for obj in objects:
        object_visibility[obj] = obj.hide_viewport
        obj.hide_viewport = True
    return object_visibility

def draw_subjects(draw_context: 'Drawing_context', draw_maker: 'Drawing_maker',
        timing_test: bool = False) -> None:
    """ Get exported svgs for every subject (or parts of it) for every style """
    drawing_times: dict[float, str] = {}
    print('Prepare drawings')
    prepare_start_time = time.time()

    cutter = draw_context.cutter
    cutter.obj.hide_viewport = False

    ## Hide all not viewed objects to make drawing faster
    subj_objs = [subj.obj for subj in draw_context.subjects]
    other_objs = [obj for obj in bpy.context.scene.objects if obj != cutter.obj]
    object_visibility = hide_objects(other_objs, subj_objs, timing_test)
    print(f'\t...completed in {(time.time() - prepare_start_time)}\n')


    ## Draw every subject
    for subject in draw_context.subjects:
        subject.obj.hide_viewport = False

        print('Drawing', subject.name)
        drawing_start_time = time.time()
        draw_maker.draw(subject, draw_context.style, cutter)
        drawing_time = time.time() - drawing_start_time
        drawing_times[drawing_time] = subject.name
        print(f"\t...drawn in {drawing_time} seconds")
        subjects.append(subject)
        subject.obj.hide_viewport = timing_test

    draw_context.cutter.delete()
    ## TODO
    ## remove new local instances created and check visibility of cutter 
    ## and subjects

    ## Restore objects visibility
    print('Restore objects visibility')
    restore_start_time = time.time()
    for obj in object_visibility:
        obj.hide_viewport = object_visibility[obj]
    print(f'\t...completed in {(time.time() - restore_start_time)}\n')

    print('\n')
    for t in sorted(drawing_times):
        print(drawing_times[t], t)
    print(f'Drawn objects in {sum(drawing_times.keys())} seconds\n')

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
    print("\n--- Completed in %s seconds ---\n\n" % 
            (time.time() - start_time))

if __name__ == "__main__":
    main()
