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
    RENDER_BASEPATH: str = bpy.path.abspath(bpy.context.scene.render.filepath)
    RENDER_RESOLUTION_X: int = bpy.context.scene.render.resolution_x
    RENDER_RESOLUTION_Y: int = bpy.context.scene.render.resolution_y
    RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

    def __init__(self, args: list[str]):
        self.args = args
        flagged_options = self.__get_flagged_options()
        self.draw_all = flagged_options['draw_all']
        self.style = flagged_options['styles']
        self.depsgraph = bpy.context.evaluated_depsgraph_get()
        self.depsgraph.update()
        selection = self.__get_objects()
        self.selected_objects = selection['objects']
        self.drawing_camera = Drawing_camera(selection['camera'], self)
        self.frame_size = self.drawing_camera.obj.data.ortho_scale
        self.subjects = self.__get_subjects(self.selected_objects)
        self.svg_size = format_svg_size(self.frame_size * 10, 
                self.frame_size * 10)
        self.svg_factor = self.frame_size/self.RENDER_RESOLUTION_X * \
                self.RESOLUTION_FACTOR
        self.svg_styles = [prj.STYLES[d_style]['name'] for d_style in 
                self.style]

    def __get_subjects(self, selection: list[bpy.types.Object]) -> \
            list[Drawing_subject]:
        """ Execute scanning to acquire the subjects to draw """
        if not selection:
            #print("Scan for visible objects...")
            #scanning_start_time = time.time()
            self.drawing_camera.scan_all()
            #scanning_time = time.time() - scanning_start_time
            #print('scan samples\n', self.drawing_camera.checked_samples)
            #print(f"   ...scanned in {scanning_time} seconds")
        else:
            #print("Scan for visibility of objects...")
            #scanning_start_time = time.time()
            for obj in selection:
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
            print('\n\nobjects_to_draw', objects_to_draw)

        ## TODO recheck this and pass value to Drawing_subject in order
        ## to handle accordingly
        instances_to_draw = {}
        for inst in self.depsgraph.object_instances:
            obj = inst.object.original
            if obj in objects_to_draw:
                instances_to_draw[obj] = {'is_instance': inst.is_instance}
        print('\n\n')
        for obj in instances_to_draw:
            print('Instance is:', obj, instances_to_draw[obj])
        print('\n\n')
        
        subjects = [Drawing_subject(obj, self) for obj in objects_to_draw]
        print('subjects', subjects)
        return subjects

    def __get_flagged_options(self) -> dict:
        """ Extract flagged values from args and return them in a dict"""
        options = ''.join([a.replace('-', '') for a in self.args 
            if a.startswith('-')])
        styles = [l for l in options if l != 'a']
        if not styles: styles = self.DEFAULT_STYLES
        return {'draw_all': 'a' in options, 'styles': styles}

    def __get_objects(self) -> tuple[list[bpy.types.Object], bpy.types.Object]:
        """ Extract the camera and renderable objects from args or selection """
        arg_objs = [a.strip() for a in self.args if not a.startswith('-')]
        all_objs = ''.join(arg_objs).split(';') if arg_objs \
                else [obj.name for obj in bpy.context.selected_objects]
        objs = []
        for ob in all_objs:
            if bpy.data.objects[ob].type == 'CAMERA':
                cam = bpy.data.objects[ob]
            elif prj.is_renderables(bpy.data.objects[ob]):
                objs.append(bpy.data.objects[ob])
        return {'objects': objs, 'camera': cam}
        
