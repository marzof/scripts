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
import prj
from prj.drawing_subject import Drawing_subject
from prj.drawing_camera import Drawing_camera
from prj import SCANNING_STEP, STYLES

import time
start_time = time.time()

format_svg_size = lambda x, y: (str(x) + 'mm', str(x) + 'mm')

class Drawing_context:
    args: list[str]
    style: str
    selected_objects: list[bpy.types.Object]
    subjects: list[Drawing_subject]
    camera: Drawing_camera 
    depsgraph: bpy.types.Depsgraph
    frame_size: float ## tuple[float, float] ... try?


    DEFAULT_STYLES: list[str] = ['p', 'c']
    FLAGS: dict[str, str] = {'draw_all': '-a', 'scanning_resolution': '-r'}
    RENDER_BASEPATH: str = bpy.path.abspath(bpy.context.scene.render.filepath)
    RENDER_RESOLUTION_X: int = bpy.context.scene.render.resolution_x
    RENDER_RESOLUTION_Y: int = bpy.context.scene.render.resolution_y
    RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

    def __init__(self, args: list[str]):
        self.args = args
        self.draw_all = False
        self.style = []
        ## TODO set scanning step in metric units
        self.scanning_resolution = SCANNING_STEP
        self.depsgraph = bpy.context.evaluated_depsgraph_get()
        self.depsgraph.update()
        object_args = self.__set_flagged_options()
        selection = self.__get_objects(object_args)
        self.selected_objects = selection['objects']
        self.drawing_camera = Drawing_camera(selection['camera'], self)
        self.drawing_camera.scanner.set_step(self.scanning_resolution)
        self.frame_size = self.drawing_camera.obj.data.ortho_scale
        self.subjects = self.__get_subjects(self.selected_objects)
        self.svg_size = format_svg_size(self.frame_size * 10, 
                self.frame_size * 10)
        self.svg_factor = self.frame_size/self.RENDER_RESOLUTION_X * \
                self.RESOLUTION_FACTOR
        self.svg_styles = [prj.STYLES[d_style]['name'] for d_style in 
                self.style]

    def __get_subjects(self, selected_objects: list[bpy.types.Object]) -> \
            list[Drawing_subject]:
        """ Execute scanning to acquire the subjects to draw """
        if not selected_objects:
            #print("Scan for visible objects...")
            #scanning_start_time = time.time()
            self.drawing_camera.scan_all()
            #scanning_time = time.time() - scanning_start_time
            #print('scan samples\n', self.drawing_camera.checked_samples)
            #print(f"   ...scanned in {scanning_time} seconds")
        else:
            #print("Scan for visibility of objects...")
            #scanning_start_time = time.time()
            for obj in selected_objects:
                ## Scan samples of previous position
                self.drawing_camera.scan_previous_obj_area(obj.name)
                ## Scan subj 
                self.drawing_camera.scan_object_area(obj)
            #print('scan samples\n', self.drawing_camera.checked_samples)
            #scanning_time = time.time() - scanning_start_time
            #print(f"   ...scanned in {scanning_time} seconds")
        objects_to_draw = self.drawing_camera.get_objects_to_draw()
        if self.draw_all:
            objects_to_draw = self.drawing_camera.get_visible_objects()


        deps_instances_data = {}
        for inst in self.depsgraph.object_instances:
            deps_inst_matrix = inst.matrix_world.copy().freeze()
            deps_inst_obj = inst.object.original
            deps_instances_data[(deps_inst_obj, deps_inst_matrix)] = {
                    'instance': inst, 'parent': inst.parent}
            
        instances_to_draw_data = {}
        for inst in objects_to_draw:
            inst_matrix = inst.matrix.freeze() 
            instances_to_draw_data[(inst.obj, inst_matrix)] = inst 

        subjects = []
        for instance_data in instances_to_draw_data:
            if instance_data in deps_instances_data:
                deps_inst = deps_instances_data[instance_data]['instance']
                parent = deps_instances_data[instance_data]['parent']
                instance = instances_to_draw_data[instance_data]
                subjects.append(Drawing_subject(instance, self, parent))

        #print('subjects', subjects)
        return subjects

    def __set_flagged_options(self) -> list[str]:
        """ Set flagged values from args and return remaining args for 
            getting objects """
        self.draw_all = self.FLAGS['draw_all'] in self.args

        options_idx = []
        flagged_args = [arg for arg in self.args if arg.startswith('-')]
        for arg in flagged_args:
            arg_idx = self.args.index(arg)
            options_idx.append(arg_idx)
            if arg == self.FLAGS['scanning_resolution']:
                self.scanning_resolution = float(self.args[arg_idx + 1])
                options_idx.append(arg_idx + 1)
                continue
            self.style += [l for l in arg if l in STYLES]

        if not self.style: 
            self.style = self.DEFAULT_STYLES
        object_args = [arg for idx, arg in enumerate(self.args) \
                if idx not in options_idx]
        return object_args

    def __get_objects(self, object_args: list[str]) -> \
            tuple[list[bpy.types.Object], bpy.types.Object]:
        """ Extract the camera and renderable objects from args or selection """
        all_objs = ''.join(object_args).split(';') if object_args \
                else [obj.name for obj in bpy.context.selected_objects]
        objs = []
        for ob in all_objs:
            if bpy.data.objects[ob].type == 'CAMERA':
                cam = bpy.data.objects[ob]
            elif prj.is_renderables(bpy.data.objects[ob]):
                objs.append(bpy.data.objects[ob])
        return {'objects': objs, 'camera': cam}
        
