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
import math
import numpy as np
from prj.utils import is_cut, is_framed, flatten, get_render_data, get_resolution
from prj.drawing_subject import Drawing_subject
from prj.drawing_camera import get_drawing_camera
from prj.working_scene import Working_scene, get_working_scene
import time

HI_RES_RENDER_FACTOR: int = 4
is_visible = lambda obj: not obj.hide_render and not obj.hide_viewport


def is_in_visible_collection(obj: bpy.types.Object) -> bool:
    ## TODO complete and use in get_framed_subjects
    for collection in obj.users_collection:
        if not collection.hide_render and not collection.hide_viewport:
            return True
        return False

def get_framed_subjects(camera: bpy.types.Object, 
        drawing_context: 'Drawing_context') -> list[Drawing_subject]:
    """ Check for all object instances in scene and return those which are 
        inside camera frame (and camera limits) as Drawing_subject(s)"""

    depsgraph = bpy.context.evaluated_depsgraph_get()
    framed_subjects = []
    for obj_inst in depsgraph.object_instances:
        print('Process', obj_inst.object.name)

        is_in_frame = is_framed(obj_inst, camera)
        ## TODO ignore objects whose users_collection are not visible too
        if not is_in_frame['result'] or not is_visible(obj_inst.object): 
            # or not is_in_visible_collection(obj_inst.object):
            continue
        ## Create the temporary Drawing_subject
        inst_name=obj_inst.object.name
        inst_library=obj_inst.object.library
        lib_path = inst_library.filepath if inst_library else inst_library
        framed_subject = Drawing_subject(
                eval_obj=bpy.data.objects[inst_name, lib_path],
                name=inst_name,
                drawing_context=drawing_context,
                mesh = bpy.data.meshes.new_from_object(obj_inst.object),
                matrix=obj_inst.object.matrix_world.copy().freeze(),
                parent=obj_inst.parent,
                is_instance=obj_inst.is_instance,
                library=inst_library,
                cam_bound_box=is_in_frame['bound_box'],
                is_in_front=is_in_frame['in_front'], 
                is_behind=is_in_frame['behind'], 
                )
        framed_subjects.append(framed_subject)
    return framed_subjects

def get_colors_spectrum(size: int) -> list[tuple[float]]:
    """ Create enough different colors (rgb_values to the third power) to cover 
        size (at least) """
    rgb_values = math.ceil(size ** (1./3))
    spectrum = np.linspace(0, 1, rgb_values)
    colors = [(r, g, b, 1) for r in spectrum for g in spectrum for b in spectrum]
    return colors

def get_separated_subjs(subject: Drawing_subject, 
        other_subjects: list[Drawing_subject]) -> list[Drawing_subject]:
    """ Take subject and get not-overlapping subjects (by bounding_rect) in
        relation to other_subjects """
    separated_subjs = [subj for subj in other_subjects \
            if subj not in subject.overlapping_subjects]
    for subj in separated_subjs[:]:
        if subj not in separated_subjs:
            continue
        for over_sub in subj.overlapping_subjects:
            if over_sub not in separated_subjs:
                continue
            separated_subjs.remove(over_sub)
    return separated_subjs

def get_render_groups(subjects: list[Drawing_subject], 
        render_groups: list= []) -> list[list[Drawing_subject]]:
    """ Create groups of not-overlapping subjects (by bounding rect) 
        and return them in a list """
    if not subjects:
        return render_groups
    if len(subjects) < 2:
        render_groups.append(subjects)
        return render_groups
    separated_subjects = get_separated_subjs(subjects[0], subjects[1:])
    render_groups.append([subjects[0]] + separated_subjects)
    next_subjects = [subj for subj in subjects 
            if subj not in flatten(render_groups)]
    return get_render_groups(next_subjects, render_groups)

def get_viewed_subjects(render_pixels: 'ImagingCore', 
        subjects: list[Drawing_subject], 
        drawing_camera: 'Drawing_camera'= None) -> list[Drawing_subject]:
    """ Filter not-visible subjects and get the a list of visible subject
        (with bounding rect calculated) """
    ## Actual colors that are in render_pixels
    viewed_colors = set(render_pixels)

    visible_subjects = []
    for subj in subjects:
        if subj.color not in viewed_colors:
            if not drawing_camera or not is_cut(subj.obj, subj.matrix, 
                    drawing_camera.frame, drawing_camera.direction):
                print(subj.name, 'is NOT VISIBLE')
                continue
        print(subj.name, 'is VISIBLE')
        if drawing_camera:
            subj.get_bounding_rect()
        visible_subjects.append(subj)
    return visible_subjects

def set_subjects_overlaps(visible_subjects: list[Drawing_subject]) -> None:
    """ Define overlapping subjects (based on actual pixels) """
    subjects_map: dict[int, list[Drawing_subject]] = {}
    for subj in visible_subjects:
        ## Clear overlapping objects based on bounding rect
        subj.overlapping_subjects = []
        for pixel in subj.render_pixels:
            if pixel not in subjects_map:
                subjects_map[pixel] = []
            subjects_map[pixel].append(subj)
    for pixel in subjects_map:
        if len(subjects_map[pixel]) < 2:
            continue
        for subj in subjects_map[pixel]:
            subj.add_overlapping_subjs(subjects_map[pixel])

def filter_selected_subjects(subjects: list[Drawing_subject],
        selected_objects: list[bpy.types.Object]) -> list [Drawing_subject]:
    """ Filter subjects based on selected_objects """
    subject_is_selected = lambda subj: subj.eval_obj.original in selected_objects
    parent_is_selected = lambda subj: subj.parent \
                and subj.parent.original in selected_objects
    selected_subjects = [subj for subj in subjects \
            if subject_is_selected(subj) or parent_is_selected(subj)] 
    return selected_subjects

def get_previous_pixels_subjects(base_subjects: list[Drawing_subject], 
        selected_subjects: list[Drawing_subject], 
        render_pixels: 'ImagingCore' = None) -> list[Drawing_subject]:
    """ Get subjects from render_pixels previously occupied by 
        selected_subjects """
    for subj in selected_subjects:
        if not subj.previous_render_pixels:
            continue
        if subj.previous_render_pixels == subj.render_pixels:
            continue
        pixels_to_check = [render_pixels[pixel] \
                for pixel in subj.previous_render_pixels]
        subjects_from_prev = get_viewed_subjects(pixels_to_check, base_subjects)
        subj.add_prev_pixels_subjects(subjects_from_prev)
       
    previous_pixels_subjects = list(set([prev_pix_subj for subj \
            in base_subjects for prev_pix_subj in subj.previous_pixels_subjects \
            if prev_pix_subj not in selected_subjects]))
    return previous_pixels_subjects

def get_raw_render_data(working_scene: Working_scene, 
        resolution: int = None) -> 'Imaging_Core':
    """ Generate raw rendering (flat colors, no anti-alias) at resolution
        in order to get a map of pixels. Reset resolution at initial value 
        after rendering """
    if resolution:
        base_resolution = working_scene.get_resolution()
        working_scene.set_resolution(resolution=resolution)
    render_pixels = get_render_data([], working_scene.scene)
    if resolution:
        working_scene.set_resolution(resolution=base_resolution)
    return render_pixels 

def get_subjects(selected_objects: list[bpy.types.Object], 
        drawing_context: 'Drawing_context') -> list[Drawing_subject]:
    """ Execute rendering to acquire the subjects to draw """
    drawing_camera = get_drawing_camera()
    working_scene = get_working_scene()
    render_resolution = drawing_context.render_resolution
    wire_drawing = drawing_context.wire_drawing

    ## Get framed objects and create temporary drawing subjects from them
    framed_subjects = get_framed_subjects(drawing_camera.obj, drawing_context)

    if drawing_context.back_drawing:
        selected_subjects = filter_selected_subjects(framed_subjects, 
                selected_objects)
        for subj in selected_subjects: 
            subj.update_status(selected=True, data=subj.drawing_context, 
                    ignore_options=drawing_context.draw_all)
        return {'selected_subjects': selected_subjects,
                'previous_pixels_subjects': [],
                'overlapping_subjects': [],
                }

    ## Create colors and assign them to framed_subjects
    colors: list[tuple[float]] = get_colors_spectrum(len(framed_subjects))
    for i, framed_subj in enumerate(framed_subjects):
        framed_subj.set_color(colors[i])

    base_res_render_data = get_raw_render_data(working_scene)
    hi_res_render_data = get_raw_render_data(working_scene, 
            render_resolution * HI_RES_RENDER_FACTOR)

    ## Filter subjects by actual visibility
    visible_subjects: list[Drawing_subject] = get_viewed_subjects(
            hi_res_render_data, framed_subjects, drawing_camera)
    ## Remove not viewed subjects and add visible ones to working_scene.subjects
    for framed_subj in framed_subjects:
        if framed_subj not in visible_subjects:
            framed_subj.remove()
        else:
            working_scene.add_subject(framed_subj)
    ## Calculate overlaps for every visible subject (based on bounding box)
    for subj in visible_subjects:
        subj.get_overlap_subjects(visible_subjects)
        
    ## Filter subjects by selection 
    selected_subjects = visible_subjects if not selected_objects else \
            filter_selected_subjects(visible_subjects, selected_objects)
    for subj in selected_subjects: 
        subj.update_status(selected=True, data=subj.drawing_context, 
                ignore_options=drawing_context.draw_all)
    ## If subjects are not actually selected (draw_all)
    ## options will not update (in order to keep previous values)

    ## Execute combined renderings to map pixels to selected_subjects
    ### Get groups of not-overlapping subjects to perfom combined renderings
    render_groups = get_render_groups(visible_subjects, [])

    ### Prepare scene
    render_scene = Working_scene(scene_name='prj_rnd', filename='prj_rnd.tif',
            resolution=render_resolution, camera=drawing_camera.obj)

    ### Execute renderings and map pixels
    renders_time = time.time()
    for subjects_group in render_groups:
        objs = [subj.obj for subj in subjects_group]
        render_pixels = get_render_data(objs, render_scene.scene)
        for subj in subjects_group:
            subj.update_render_pixels(render_pixels)
    print('Render selected_subjects in', time.time() - renders_time)

    ## Define exact overlaps for every subject and add overlapping subjects to
    ## subjects if selection
    set_subjects_overlaps(visible_subjects)


    if selected_objects:
        ## Get subjects from previous position
        previous_pixels_subjects = get_previous_pixels_subjects(visible_subjects,
                selected_subjects, base_res_render_data)
        overlapping_subjects = [over_subj for subj in selected_subjects 
                for over_subj in subj.overlapping_subjects \
                        if over_subj not in selected_subjects]
    else:
        previous_pixels_subjects = []
        overlapping_subjects = []

    print('Subjects detection in:', time.time() - renders_time)
    render_scene.remove()

    return {'selected_subjects': selected_subjects,
            'previous_pixels_subjects': previous_pixels_subjects,
            'overlapping_subjects': overlapping_subjects,
            }

