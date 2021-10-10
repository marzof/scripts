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
from prj.utils import is_cut, is_framed, flatten, get_render_data, name_cleaner
from prj.drawing_subject import Drawing_subject
from prj.drawing_camera import get_drawing_camera
from prj.working_scene import Working_scene, get_working_scene
from mathutils import Vector
import time

## TODO review the entire code and try to make it more readable
HI_RES_RENDER_FACTOR: int = 4
checked_objs = []
is_visible = lambda obj: not obj.hide_render and not obj.hide_viewport \
        and not obj.hide_get()

def is_parallel_to_camera(obj: bpy.types.Object,
        drawing_camera: 'Drawing_camera') -> bool:
    """ Check if obj z axis is parallel to drawing_camera z axis """
    mat = obj.matrix_world
    obj_Z_axis = Vector((mat[0][2],mat[1][2],mat[2][2]))
    dot_product = obj_Z_axis @ drawing_camera.direction
    if round(abs(dot_product), 5) == 1:
        return True

def get_object_collections(obj: bpy.types.Object, scene_tree: dict[tuple[int], 
    bpy.types.Collection]) -> dict[bpy.types.Collection, list[str]]:
    """ Get the collections obj belongs to (based on scene_tree)"""
    global checked_objs
    obj_inst_collections = {}
    tmp_collections = []
    positions = 0
    for position in scene_tree:
        if scene_tree[position] != obj:
            continue
        checked_objs.append(obj)
        parent_collection = scene_tree[position[:-1]]
        positions += 1
        ## For obj in position like (0, 0, 2, 1, 0, 1) get collections at 
        ##      position: (0,0), (0,0,2), (0,0,2,1), (0,0,2,1,0)
        for i in range(2, len(position)):
            collection = scene_tree[position[:i]]
            tmp_collections.append(scene_tree[position[:i]])
    ## If a collection is STRONG when it is hidden its objects are hidden too
    ## If the collection is WEAK then its objects remain visible even when 
    ##      the collection is hidden
    for coll in tmp_collections:
        if tmp_collections.count(coll) < positions:
            obj_inst_collections[coll] = ['WEAK']
        else:
            obj_inst_collections[coll] = ['STRONG']
        if coll == parent_collection:
            obj_inst_collections[coll].append('PARENT')
    return obj_inst_collections

def get_framed_subjects(camera: bpy.types.Object, 
        drawing_context: 'Drawing_context') -> list[Drawing_subject]:
    """ Check for all object instances in scene and return those which are 
        inside camera frame (and camera limits) as Drawing_subject(s)"""

    global checked_objs
    depsgraph = bpy.context.evaluated_depsgraph_get()
    framed_subjects = []
    scene_tree = drawing_context.scene_tree

    for obj_inst in depsgraph.object_instances:
        print('Process', obj_inst.object.name)

        ## Check if obj_inst is inside camera frame
        is_in_frame = is_framed(obj_inst, camera)
        if not is_in_frame['result']:
            continue

        inst_name = obj_inst.object.name
        inst_library = obj_inst.object.library
        lib_path = inst_library.filepath if inst_library else inst_library
        eval_obj = bpy.data.objects[inst_name, lib_path]
        symbol_type = None if obj_inst.object.prj_symbol_type == 'none' \
                else obj_inst.object.prj_symbol_type 

        ## Detect actual object to process (obj_inst.obj or its parent)
        if eval_obj not in scene_tree.values():
            tree_obj = bpy.data.objects[obj_inst.parent.name]
            if tree_obj in checked_objs:
                continue
        else:
            tree_obj = eval_obj

        ## Filter not well oriented symbols (Z axis of tree_obj has to be 
        ## parallel to camera direction)
        if symbol_type and not is_parallel_to_camera(tree_obj, 
            drawing_context.drawing_camera):
            continue

        ## Don't draw symbols in back view
        if drawing_context.back_drawing and symbol_type:
            continue

        ## Not proceeding if object is not visible
        if not is_visible(tree_obj) and not symbol_type:
            continue

        ## Get object collections and check collections visibility
        obj_inst_collections = get_object_collections(tree_obj, scene_tree)
        checked_objs.clear() ## TODO check why clear now
        #print(obj_inst.object.name, obj_inst_collections)
        collections_hide_status = [(coll.hide_render or coll.hide_viewport) \
                for coll in obj_inst_collections \
                if 'STRONG' in obj_inst_collections[coll]]
        ## If any (STRONG) obj_inst collection is hidden then ignore the obj_inst
        if any(collections_hide_status):
            continue

        ## Create the temporary Drawing_subject
        framed_subject = Drawing_subject(
                eval_obj=bpy.data.objects[inst_name, lib_path],
                name=name_cleaner(inst_name),
                drawing_context=drawing_context,
                mesh = bpy.data.meshes.new_from_object(obj_inst.object),
                matrix=obj_inst.object.matrix_world.copy().freeze(),
                parent=obj_inst.parent,
                is_instance=obj_inst.is_instance,
                library=inst_library,
                cam_bound_box=is_in_frame['bound_box'],
                is_in_front=is_in_frame['in_front'], 
                is_behind=is_in_frame['behind'], 
                collections=obj_inst_collections,
                symbol_type=symbol_type,
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
        if subj.color not in viewed_colors and not subj.is_symbol:
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
    selected_subjects = []
    for subj in subjects:
        subj_is_selected = subj.eval_obj.original in selected_objects
        parent_is_selected = subj.parent and subj.parent.original \
                in selected_objects
        if subj_is_selected or parent_is_selected or subj.is_symbol:
            selected_subjects.append(subj)
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

    base_res_render_data = get_render_data([], working_scene.scene)
    working_scene.set_resolution_percentage(
            HI_RES_RENDER_FACTOR * working_scene.DEFAULT_RESOLUTION_PERCENTAGE)
    hi_res_render_data = get_render_data([], working_scene.scene)
    working_scene.set_resolution_percentage(
            working_scene.DEFAULT_RESOLUTION_PERCENTAGE)

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
        if subj.is_symbol:
            continue
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

