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
import re
import prj
from prj.drawing_subject import Drawing_subject
from prj.drawing_camera import Drawing_camera, SCANNING_STEP
import time

STYLES = {
        'p': {'name': 'prj', 'occlusion_start': 0, 'occlusion_end': 1,
            'chaining_threshold': 0, 'condition': 'is_in_front'},
        'c': {'name': 'cut', 'occlusion_start': 0, 'occlusion_end': 128,
            'chaining_threshold': 0, 'condition': 'is_cut'},
        'h': {'name': 'hid', 'occlusion_start': 1, 'occlusion_end': 128,
            'chaining_threshold': 0, 'condition': 'is_in_front'},
        'b': {'name': 'bak', 'occlusion_start': 0, 'occlusion_end': 128,
            'chaining_threshold': 0, 'condition': 'is_behind'},
        }
is_renderables = lambda obj: (obj.type, bool(obj.instance_collection)) \
        in [('MESH', False), ('CURVE', False), ('EMPTY', True)]

start_time = time.time()

format_svg_size = lambda x, y: (str(x) + 'mm', str(x) + 'mm')
UNIT_FACTORS = {'m': 1, 'cm': 100, 'mm': 1000}

class Drawing_context:
    RENDER_BASEPATH: str
    RENDER_RESOLUTION_X: int
    RENDER_RESOLUTION_Y: int
    args: list[str]
    style: str
    scan_resolution: dict
    selected_objects: list[bpy.types.Object]
    subjects: list[Drawing_subject]
    camera: Drawing_camera 
    depsgraph: bpy.types.Depsgraph
    frame_size: float ## tuple[float, float] ... try?


    DEFAULT_STYLES: list[str] = ['p', 'c']
    FLAGS: dict[str, str] = {'draw_all': '-a', 'scan_resolution': '-r'}
    RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

    def __init__(self, args: list[str], context):
        self.RENDER_BASEPATH = bpy.path.abspath(context.scene.render.filepath)
        self.RENDER_RESOLUTION_X = context.scene.render.resolution_x
        self.RENDER_RESOLUTION_Y = context.scene.render.resolution_y
        self.context = context
        self.args = args
        self.draw_all = False
        self.style = []
        self.scan_resolution = {'value': SCANNING_STEP, 'units': None}
        self.depsgraph = context.evaluated_depsgraph_get()
        self.depsgraph.update()
        object_args = self.__set_flagged_options()
        selection = self.__get_objects(object_args)
        self.selected_objects = selection['objects']
        self.drawing_camera = Drawing_camera(selection['camera'], self)
        self.drawing_camera.scanner.set_step(self.get_scan_step())
        self.frame_size = self.drawing_camera.obj.data.ortho_scale
        self.subjects = self.__get_subjects(self.selected_objects)
        self.svg_size = format_svg_size(self.frame_size * 10, 
                self.frame_size * 10)
        self.svg_factor = self.frame_size/self.RENDER_RESOLUTION_X * \
                self.RESOLUTION_FACTOR
        self.svg_styles = [STYLES[d_style]['name'] for d_style in 
                self.style]

    def __get_subjects(self, selected_objects: list[bpy.types.Object]) -> \
            list[Drawing_subject]:
        """ Execute scanning to acquire the subjects to draw """
        if not selected_objects:
            self.drawing_camera.scan_all()
        else:
            for obj in selected_objects:
                self.drawing_camera.scan_previous_obj_area(obj.name)
                self.drawing_camera.scan_object_area(obj)
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

    def set_scan_resolution(self, raw_resolution: str) -> None:
        """ Set scan_resolution based on raw_resolution arg """
        search = re.search(r'[a-zA-Z]+', raw_resolution)
        if search:
            index = search.span()[0]
            value = float(raw_resolution[:index])
            units = search.group(0).lower()
        else:
            value = float(raw_resolution)
            units = None
        self.scan_resolution = {'value': value, 'units': units}

    def get_scan_step(self) -> float:
        """ Calculate scanning step and return it """
        value = self.scan_resolution['value']
        units = self.scan_resolution['units']
        cam_frame = self.drawing_camera.ortho_scale
        if units:
            factor = UNIT_FACTORS[units]
            return (value /factor) / cam_frame
        return float(value)

    def __set_flagged_options(self) -> list[str]:
        """ Set flagged values from args and return remaining args for 
            getting objects """
        self.draw_all = self.FLAGS['draw_all'] in self.args

        options_idx = []
        flagged_args = [arg for arg in self.args if arg.startswith('-')]
        for arg in flagged_args:
            arg_idx = self.args.index(arg)
            options_idx.append(arg_idx)
            if arg == self.FLAGS['scan_resolution']:
                raw_resolution = self.args[arg_idx + 1]
                self.set_scan_resolution(raw_resolution)
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
        args_objs = ''.join(object_args).split(';')
        selected_objs = self.context.selected_objects
        cam = None
        objs = []
        for ob in args_objs:
            if ob and bpy.data.objects[ob].type == 'CAMERA':
                cam = bpy.data.objects[ob]
            elif ob and is_renderables(bpy.data.objects[ob]):
                objs.append(bpy.data.objects[ob])
        for ob in selected_objs:
            if not cam and ob.type == 'CAMERA':
                cam = ob
            elif not objs and is_renderables(ob):
                objs.append(ob)
        return {'objects': objs, 'camera': cam}
        
