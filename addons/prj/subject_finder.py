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

is_visible = lambda obj: not obj.hide_render and not obj.hide_viewport


def is_in_visible_collection(obj: bpy.types.Object) -> bool:
    ## TODO complete and use in get_framed_subjects
    for collection in obj.users_collection:
        if not collection.hide_render and not collection.hide_viewport:
            return True
        return False

def get_framed_subjects(camera: bpy.types.Object) -> list[Drawing_subject]:
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
                #print(subj.name, 'is NOT VISIBLE')
                continue
        #print(subj.name, 'is VISIBLE')
        if drawing_camera:
            subj.get_bounding_rect()
        visible_subjects.append(subj)
    return visible_subjects

def update_pixel_maps(subject: Drawing_subject, render_pixels: 'ImagingCore', 
        subjects_map: dict[int, list[Drawing_subject]], 
        render_resolution: int) -> None:
    """ Populate subject.render_pixels and subjects_map by subject(s) 
        render_pixels """
    subj_pixels = subject.get_area_pixels(render_resolution)
    for pixel in subj_pixels:
        if render_pixels[pixel][3] != 255:
            continue
        if pixel not in subjects_map:
            subjects_map[pixel] = []
        subject.add_render_pixel(pixel)
        subjects_map[pixel].append(subject)

def set_overlaps(subjects_map) -> None:
    """ Define overlapping subjects (based on actual pixels) """
    for pixel in subjects_map:
        if len(subjects_map[pixel]) < 2:
            continue
        for subj in subjects_map[pixel]:
            subj.add_overlapping_subjs(subjects_map[pixel])

def get_actual_subjects(base_subjects: list[Drawing_subject], 
        selected_objects: list[bpy.types.Object], styles: list[str],
        render_pixels: 'ImagingCore' = None ) -> list[Drawing_subject]:
    """ Filter base_subjects according to styles """
    ## no_selection (draw_all) -> subjects = all subjects (visible_subjects)
    ## hidden | back (selection needed) -> subjects = just selected_objects
    ## proj/cut (with selection, otherwise draw_all) -> subjects = \
    ##         selected_objects + occluded_objects + previous_pixels_objects
    
    subjects = []
    if len(selected_objects) == 0:      ## draw_all
        for subj in base_subjects:
            subjects.append(subj)
            subj.get_overlap_subjects(base_subjects)
        return subjects

    for subj in base_subjects:
        subj.get_overlap_subjects(base_subjects)
        subject_is_selected = subj.eval_obj.original in selected_objects
        parent_is_selected = subj.parent \
                and subj.parent.original in selected_objects
        if not subject_is_selected and not parent_is_selected: 
            continue
        subjects.append(subj)
        if 'h' in styles or 'b' in styles:
            return subjects

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
            if prev_pix_subj not in subjects]))
    return subjects + previous_pixels_subjects

def get_subjects(selected_objects: list[bpy.types.Object], drawing_scale: float,
        drawing_styles: list[str]) -> list[Drawing_subject]:
    """ Execute rendering to acquire the subjects to draw """
    drawing_camera:'Drawing_camera' = get_drawing_camera()
    render_resolution = get_resolution(drawing_camera.ortho_scale, drawing_scale)

    ## Get framed objects and create temporary drawing subjects from them
    tmp_subjects: list[Drawing_subject] = get_framed_subjects(drawing_camera.obj)

    ## Create colors and assign them to tmp_subjects
    colors: list[tuple[float]] = get_colors_spectrum(len(tmp_subjects))
    for i, tmp_subj in enumerate(tmp_subjects):
        tmp_subj.set_color(colors[i])

    ## Generate a raw_render (flat colors, no anti-alias)
    working_scene = get_working_scene()
    main_resolution = working_scene.get_resolution()
    ## TODO Apply (and reset after) prj.drawing_context.RENDER_FACTOR here, 
    ## not in drawing_context
    ## working_scene.set_resolution(drawing_camera.ortho_scale, drawing_scale)
    flat_render_pixels = get_render_data([], working_scene.scene)

    ## Filter subjects by actual visibility
    visible_subjects: list[Drawing_subject] = get_viewed_subjects(
            flat_render_pixels, tmp_subjects, drawing_camera)

    base_render_pixels = None
    if selected_objects:
        ## Generate a raw_render at actual resolution
        working_scene.set_resolution(drawing_camera.ortho_scale, drawing_scale)
        base_render_pixels = get_render_data([], working_scene.scene)
        working_scene.set_resolution(resolution=main_resolution)
    
    ## Filter subjects by selection and get overlapping subjects 
    ## (based on bounding rectangle)
    subjects: list[Drawing_subject] = get_actual_subjects(visible_subjects, 
            selected_objects, drawing_styles, base_render_pixels)

    ## Remove not viewed subjects (at present and in previous version)
    for tmp_subj in tmp_subjects:
        if tmp_subj not in visible_subjects and tmp_subj not in subjects:
            tmp_subj.remove()

    ### Get groups of not-overlapping subjects to perfom combined renderings
    render_groups = get_render_groups(visible_subjects)
    print('groups are', len(render_groups), '\nsubjects are', len(subjects))
    print('groups content is', render_groups, 
            '\nvisible subjects are', len(visible_subjects))

    ## Execute combined renderings to map pixels to subjects
    ### Prepare scene
    render_scene = Working_scene('prj_rnd', 'prj_rnd.tif')
    render_scene.set_resolution(resolution=render_resolution)
    render_scene.link_object(drawing_camera.obj)
    render_scene.scene.camera = drawing_camera.obj

    ### Execute renderings and map pixels
    renders_time = time.time()
    ## A dict to map pixel number (an int) to lists of overlapping subjects
    subjects_map: dict[int, list[Drawing_subject]] = {}
    ## TODO check if it's possible to reduce renderings if not draw_all
    ##      and avoid them if style is hidden or back (check if a dedicated
    ##      process for styles is convenient)
    for subjects_group in render_groups:
        objs = [subj.obj for subj in subjects_group]
        render_pixels = get_render_data(objs, render_scene.scene)
        for subj in subjects_group:
            ## Clear overlapping objects based on bounding rect
            subj.overlapping_subjects = []
            update_pixel_maps(subj, render_pixels, subjects_map, 
                    render_resolution)
    print('Render subjects in', time.time() - renders_time)

    ## Define exact overlaps for every subject and add overlapping subjects to
    ## subjects if selection
    set_overlaps(subjects_map)
    ## TODO clean up here
    if len(selected_objects) > 0 and \
            ('c' in drawing_styles or 'p' in drawing_styles):
        for subj in subjects:
            for over_subj in subj.overlapping_subjects:
                if over_subj not in subjects:
                    subjects.append(over_subj)
    
    print('Subjects detection in:', time.time() - renders_time)
    render_scene.remove()

    return subjects

