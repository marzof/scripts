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
from prj.utils import is_cut, is_framed
from prj.drawing_subject import Drawing_subject
from prj.working_scene import get_working_scene
import time

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
        framed_subject = Drawing_subject(
                eval_obj=obj_inst.object,
                name=obj_inst.object.name,
                mesh = bpy.data.meshes.new_from_object(obj_inst.object),
                matrix=obj_inst.object.matrix_world.copy().freeze(),
                parent=obj_inst.parent,
                is_instance=obj_inst.is_instance,
                library=obj_inst.object.library,
                cam_bound_box=is_in_frame['bound_box'],
                is_in_front=is_in_frame['in_front'], 
                is_behind=is_in_frame['behind'], 
                draw_context=drawing_context, 
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

def flatten(t):
    return [item for sublist in t for item in sublist]

class Camera_viewer:
    def __init__(self, drawing_camera: 'Drawing_camera', 
            drawing_context: 'Drawing_context'):
        self.drawing_camera = drawing_camera
        self.drawing_context = drawing_context

    def get_subjects(self, selected_objects: list[bpy.types.Object]) -> \
            list[Drawing_subject]:
        """ Execute rendering to acquire the subjects to draw """
        working_scene = get_working_scene()
        
        ## Get framed objects and create temporary drawing subjects from them
        tmp_subjects = get_framed_subjects(self.drawing_camera.obj, 
                self.drawing_context)

        ## Create colors and assign them to tmp_subjects
        colors = get_colors_spectrum(len(tmp_subjects))
        for i, tmp_subj in enumerate(tmp_subjects):
            tmp_subj.set_color(colors[i])

        ## Execute render
        render_time = time.time()
        bpy.ops.render.render(write_still=True, scene=working_scene.name)
        print('Render scene in', time.time() - render_time)
        
        ## Get colors from render
        get_color_time = time.time()
        wb_render = Image.open(working_scene.render.filepath)
        viewed_colors = set(wb_render.getdata())
        print('Get colors in', time.time() - get_color_time)
        

        ## Filter subjects and get the actual list 
        ## (with bounding rect calculated)
        subjects = []
        for tmp_subj in tmp_subjects:
            if tmp_subj.color not in viewed_colors:
                if not is_cut(tmp_subj.obj, tmp_subj.matrix, 
                        self.drawing_camera.frame, 
                        self.drawing_camera.direction):
                    print(tmp_subj.name, 'is not in: SKIP IT')
                    tmp_subj.remove()
                    continue
            print(tmp_subj.name, 'is in: TAKE IT')
            tmp_subj.get_bounding_rect()
            subjects.append(tmp_subj)

        ### for subject in subjects:
        ###     subject.get_overlap_subjects(subjects)

        from prj.working_scene import Working_scene
        from prj.working_scene import RENDER_RESOLUTION_X as X
        render_scene = Working_scene('prj_rnd', 'prj_rnd.tif').scene
        render_scene.collection.objects.link(self.drawing_camera.obj)
        render_scene.camera = self.drawing_camera.obj

        subjects_map = {}

        renders_time = time.time()
        for subj in subjects:
            print('Render for', subj.name, subj.color)
            render_scene.collection.objects.link(subj.obj)
            bpy.ops.render.render(write_still=True, scene=render_scene.name)
            render_scene.collection.objects.unlink(subj.obj)

            wb_tmp_render = Image.open(render_scene.render.filepath)
            viewed_colors = wb_tmp_render.getdata()

            bound_rect_x = subj.bounding_rect[0].x
            bound_rect_y = subj.bounding_rect[2].y
            bound_width = subj.bounding_rect[2].x - subj.bounding_rect[0].x
            bound_height = subj.bounding_rect[2].y - subj.bounding_rect[0].y
            px_from_x = math.floor(X * bound_rect_x)
            px_from_y = X - math.ceil(X * bound_rect_y)
            px_width = math.ceil(X * bound_width)
            px_height = math.ceil(X * bound_height)
            pixels = flatten([list(range(px_from_x+(X*y), 
                px_from_x+(X*y)+px_width)) for y in range(px_from_y, 
                    px_from_y + px_height)])
            #print(pixels[0], pixels[-1])
            for pixel in pixels:
                if viewed_colors[pixel][3] == 255:
                    if pixel not in subjects_map:
                        subjects_map[pixel] = []
                    subjects_map[pixel].append(subj)
        r_t = time.time() - renders_time
        overlaps = []
        for pixel in subjects_map:
            if len(subjects_map[pixel]) > 1:
                pix_val = [subj for subj in subjects_map[pixel]]
                if pix_val not in overlaps:
                    overlaps.append(pix_val)
        for overlap in overlaps:
            for subj in overlap:
                subj.get_overlap_subjects(overlap)
        #print(overlaps)
        #print(len(subjects_map))
        print('Render subjects in', r_t)
        #raise Exception('STOP')

        return subjects

