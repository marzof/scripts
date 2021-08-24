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
from PIL import Image
from prj.utils import is_cut, is_framed, flatten
from prj.drawing_subject import Drawing_subject
from prj.drawing_camera import get_drawing_camera
from prj.working_scene import Working_scene, get_working_scene
import time

## A dict to map pixel number (an int) to lists of overlapping subjects
subjects_map: dict[int, list[Drawing_subject]] = {}
is_visible = lambda obj: not obj.hide_render and not obj.hide_viewport

render_resolution = None

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
        relation to other_subjects. 
        Return a list with subject and separated subjects """
    separated_subjs = [subj for subj in other_subjects \
            if subj not in subject.overlapping_objects]
    for subj in separated_subjs[:]:
        if subj not in separated_subjs:
            continue
        for over_sub in subj.overlapping_objects:
            if over_sub not in separated_subjs:
                continue
            separated_subjs.remove(over_sub)
    return [subject] + separated_subjs

def get_render_groups(subjects: list[Drawing_subject], 
        render_groups: list= []) -> list[list[Drawing_subject]]:
    """ Create groups of not-overlapping subjects (by bounding rect) 
        and return them in a list """
    if len(subjects) < 2:
        render_groups.append(subjects)
        return render_groups
    separated_subjects = get_separated_subjs(subjects[0], subjects[1:])
    render_groups.append(separated_subjects)
    return get_render_groups([subj for subj in subjects \
            if subj not in flatten(render_groups)], render_groups)

def get_raw_render() -> 'PIL.TiffImagePlugin.TiffImageFile':
    working_scene = get_working_scene().scene
    #render_time = time.time()
    bpy.ops.render.render(write_still=True, scene=working_scene.name)
    #print('Render scene in', time.time() - render_time)
    return Image.open(working_scene.render.filepath)

def get_viewed_subjects(raw_render: 'PIL.TiffImagePlugin.TiffImageFile', 
        subjects: list[Drawing_subject], 
        drawing_camera: 'Drawing_camera') -> list[Drawing_subject]:
    """ Filter not-visible subjects and get the actual list of subject
        (with bounding rect calculated) """

    ## Actual colors that are in raw_render
    viewed_colors = set(raw_render.getdata())

    visible_subjects = []
    for subj in subjects:
        if subj.color not in viewed_colors:
            if not is_cut(subj.obj, subj.matrix, 
                    drawing_camera.frame, 
                    drawing_camera.direction):
                #print(subj.name, 'is not in: SKIP IT')
                subj.remove()
                continue
        #print(subj.name, 'is in: TAKE IT')
        subj.get_bounding_rect()
        visible_subjects.append(subj)
    return visible_subjects

def map_subjects(subjects: list[Drawing_subject], 
        scene: bpy.types.Scene) -> None:
    """ Render the subjects group and get the pixels actually painted 
        in order to populate subjects_map """

    global subjects_map
    
    ### Move subjects to render_scene, render them and remove from scene
    #print('Render for', group) 
    for subj in subjects:
        scene.collection.objects.link(subj.obj)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    for subj in subjects:
        scene.collection.objects.unlink(subj.obj)

    ### Get the rendering data
    render = Image.open(scene.render.filepath)
    render_pixels = render.getdata()

    for subj in subjects:
        update_pixel_maps(subj, render_pixels)

def update_pixel_maps(subject: Drawing_subject, 
        render_pixels: 'ImagingCore') -> None:
    """ Populate subject.render_pixels and subjects_map """

    ## Clear overlapping objects based on bounding rect
    subject.overlapping_objects = []
    
    subj_pixels = subject.get_area_pixels(render_resolution)
    for pixel in subj_pixels:
        if render_pixels[pixel][3] != 255:
            continue
        if pixel not in subjects_map:
            subjects_map[pixel] = []
        subject.add_render_pixel(pixel)
        subjects_map[pixel].append(subject)

def set_overlaps() -> None:
    """ Define overlapping subjects (based on actual pixels) """
    for pixel in subjects_map:
        if len(subjects_map[pixel]) < 2:
            continue
        for subj in subjects_map[pixel]:
            subj.add_overlapping_objs(subjects_map[pixel])

def get_subjects(selected_objects: list[bpy.types.Object], 
        drawing_scale: float) -> list[Drawing_subject]:
    """ Execute rendering to acquire the subjects to draw """

    global render_resolution
    drawing_camera:'Drawing_camera' = get_drawing_camera()

    ## Get framed objects and create temporary drawing subjects from them
    tmp_subjects: list[Drawing_subject] = get_framed_subjects(drawing_camera.obj)

    ## Create colors and assign them to tmp_subjects
    colors: list[tuple[float]] = get_colors_spectrum(len(tmp_subjects))
    for i, tmp_subj in enumerate(tmp_subjects):
        tmp_subj.set_color(colors[i])

    ## Generate a raw_render (flat colors, no anti-alias)
    raw_render: 'PIL.TiffImagePlugin.TiffImageFile' = get_raw_render()

    subjects = get_viewed_subjects(raw_render, tmp_subjects, drawing_camera)
    
    ## Define overlapping subjects (based on bounding rectangle)
    selected_subjects = []
    draw_all = len(selected_objects) == 0
    for subject in subjects:
        print('Subj', subject.obj)
        subject_is_selected = subject.eval_obj.original in selected_objects
        parent_is_selected = subject.parent \
                and subject.parent.original in selected_objects
        if subject_is_selected or parent_is_selected or draw_all:
            selected_subjects.append(subject)
            subject.get_overlap_subjects(subjects)
    for sel_subj in selected_subjects:
        for over_subj in sel_subj.overlapping_objects:
            if over_subj in selected_subjects:
                continue
            selected_subjects.append(over_subj)
    ## TODO add objects which are changed based on info on svg
    ##      Handle as well selection for hide and back

    ### Get groups of not-overlapping subjects to perfom combined renderings
    render_groups = get_render_groups(selected_subjects)
    print('groups are', len(render_groups), '\nsubjects are', 
            len(selected_subjects))

    ## Execute combined renderings to map pixels to subjects
    ### Prepare scene
    render_scene = Working_scene('prj_rnd', 'prj_rnd.tif')
    render_resolution = render_scene.set_resolution(drawing_camera.ortho_scale, 
            drawing_scale)
    render_scene.link_object(drawing_camera.obj)
    render_scene.scene.camera = drawing_camera.obj

    renders_time = time.time()
    for subjects_group in render_groups:
        map_subjects(subjects_group, render_scene.scene)
    print('Render subjects in', time.time() - renders_time)

    ## Define exact overlaps for every subject
    set_overlaps()
    
    print('Subjects detection in:', time.time() - renders_time)
    render_scene.remove()

    return selected_subjects

