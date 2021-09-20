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
import sys, os
import prj
from pathlib import Path as Filepath
from prj.svg_path import svgs_data
from prj.svgread import Svg_read
from prj.svg_handling import prepare_composition, prepare_obj_svg
from prj.svg_handling import filter_subjects_for_svg, add_subjects_as_use
from prj.drawing_context import get_drawing_context, is_renderables
from prj.drawing_camera import get_drawing_camera
from prj.drawing_maker import draw
from prj.drawing_subject import get_subjects_list
from prj.drawing_style import create_drawing_styles, drawing_styles
from prj.cutter import get_cutter
from prj.utils import flatten
from prj.working_scene import get_working_scene
import time

drawings: list['Svg_drawing'] = []

def set_subjects_visibility(subject: 'Drawing_subject', 
        cutter: 'Cutter') -> None:
    """ Hide and show subjects depending on situation """
    subject.obj.hide_viewport = False
    overlapping_subjects = subject.overlapping_subjects
    drawing_subjects = get_subjects_list()
    for other_subj in drawing_subjects:
        if other_subj == subject:
            continue
        if other_subj == cutter:
            continue
        if subject.xray_drawing:
            other_subj.obj.hide_viewport = True
            continue
        if other_subj.xray_drawing:
            other_subj.obj.hide_viewport = True
            continue
        if other_subj not in overlapping_subjects:
            other_subj.obj.hide_viewport = True
            continue
        other_subj.obj.hide_viewport = False

def draw_subjects(subjects: list['Drawing_subject'], 
        scene: bpy.types.Scene) -> None:
    """ Get exported svgs for every subject (or parts of it) for every style """
    drawing_times: dict[float, str] = {}
    print('Prepare drawings')
    prepare_start_time = time.time()

    cutter = get_cutter()
    cutter.obj.hide_viewport = False

    draw_time = time.time()
    ## Draw every subject (and hide not overlapping ones)
    for subject in subjects:
        drawing_start_time = time.time()
        print('Drawing', subject.name)

        set_subjects_visibility(subject, cutter)
        draw(subject, cutter, scene)

        ## It misses same-time drawing objects
        drawing_time = time.time() - drawing_start_time
        drawing_times[drawing_time] = subject.name
        print(f"\t...drawn in {drawing_time} seconds")

    draw_time = time.time() - draw_time
    print('\n')
    for t in sorted(drawing_times):
        print(drawing_times[t], t)
    print(f"***Drawings completed in {draw_time} seconds")
    return 

def rewrite_svgs(subjects: list['Drawing_subject']) -> None:
    """ Get a single and organized svg for every subject """
    print('Start rewriting svg')
    draw_context = get_drawing_context()
    rewrite_svgs_start_time = time.time()
    for svg_data in svgs_data:
        drawing_start_time = time.time()
        drawing_data = svgs_data[svg_data]
        for subject in drawing_data.objects:
            if subject not in subjects:
                continue
            abstract_subj_svg = prepare_obj_svg(draw_context, drawing_data)
            subj_svg = abstract_subj_svg.to_real(drawing_data.path)
            with open(svg_data, "a") as svg_file:
                append_subject_data(svg_file, drawing_data)
            drawings.append(drawing_data.path)
    print(f'\t...completed in {(time.time() - rewrite_svgs_start_time)}\n')

def append_subject_data(svg_file: 'io.TextIOWrapper', 
        drawing_data: 'Svg_path') -> None:
    """ Append data about subject in svg_file """
    svg_file.write("<!--" + os.linesep)
    for subject in drawing_data.objects:
        svg_file.write(f'{{')
        svg_file.write(f'"subject": "{subject.name}",')
        svg_file.write(os.linesep)
        svg_file.write(f'"resolution": {subject.render_resolution},')
        svg_file.write(os.linesep)
        svg_file.write(f'"xray_drawing": {subject.xray_drawing},')
        svg_file.write(os.linesep)
        svg_file.write(f'"draw_outline": {subject.draw_outline},')
        svg_file.write(os.linesep)
        svg_file.write(f'"wire_drawing": {subject.wire_drawing},')
        svg_file.write(os.linesep)
        svg_file.write(f'"back_drawing": {subject.back_drawing},')
        svg_file.write(os.linesep)
        svg_file.write('"overlaps": [')
        for over_subj in subject.overlapping_subjects:
            lib = '"' + over_subj.library.filepath + '"' if over_subj.library \
                    else None
            svg_file.write(f'("{over_subj.name}", {lib}),')
        svg_file.write('],')
        svg_file.write(os.linesep)
        ## pixel are collected in ranges with first and last included
        svg_file.write(f'"render_pixels": {subject.pixels_range},')
        svg_file.write(f'}}')
        svg_file.write(os.linesep)
    svg_file.write("-->")

def get_svg_composition(subjects: list['Drawing_subject']) -> None:
    """ Collect every subject svg in a single composed svg 
        or add new subject to existing composed svg """
    ## TODO check why a lot of defs elements are created
    print('Start composition')
    draw_context = get_drawing_context()
    draw_camera = get_drawing_camera()
    composition_start_time = time.time()
    composition_filepath = Filepath(draw_camera.path + '.svg')
    ## TODO try to set cm as display units of svg 
    if not composition_filepath.is_file() or draw_context.draw_all:
    #if False:
        abstract_composition = prepare_composition(draw_context, subjects)
    else:
        existing_composition = Svg_read(composition_filepath)
        new_subjects = filter_subjects_for_svg(existing_composition, subjects)
        ## TODO adding hidden drawing recreate original too (so it appears twice)
        if new_subjects:
            for d_style in drawing_styles:
                style = drawing_styles[d_style].name
                containers = existing_composition.get_svg_elements('g', 
                        'inkscape:label', style)
                if not containers:
                    continue
                add_subjects_as_use(new_subjects, d_style, containers[0])
        abstract_composition = existing_composition.drawing
    composition = abstract_composition.to_real(composition_filepath)
    print(f'\t...completed in {(time.time() - composition_start_time)}\n')


def main() -> None:
    print('Start now')
    start_time = time.time()
    args = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
    create_drawing_styles()
    draw_context = get_drawing_context(args)
    if draw_context.back_drawing:
        draw_context.drawing_camera.reverse_cam()
    all_subjects = list(set(flatten(draw_context.subjects.values())))
    working_scene = get_working_scene().scene
    bpy.context.window.scene = working_scene
    draw_subjects(all_subjects, working_scene)
    rewrite_svgs(all_subjects)
    get_svg_composition(all_subjects)
    draw_context.remove()
    print("\n--- Completed in %s seconds ---\n\n" % (time.time() - start_time))

if __name__ == "__main__":
    main()
