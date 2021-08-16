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
from prj.drawing_camera import Drawing_camera
from prj.camera_viewer import Camera_viewer
from prj.drawing_style import drawing_styles
from prj.working_scene import RENDER_RESOLUTION_X
import time

is_renderables = lambda obj: (obj.type, bool(obj.instance_collection)) \
        in [('MESH', False), ('CURVE', False), ('EMPTY', True)]
format_svg_size = lambda x, y: (str(x) + 'mm', str(x) + 'mm')

class Drawing_context:
    args: list[str]
    draw_all: bool
    style: list[str]
    selected_objects: list[bpy.types.Object]
    subjects: list['Drawing_subject']
    camera: Drawing_camera 

    DEFAULT_STYLES: list[str] = ['p', 'c']
    FLAGS: dict[str, str] = {'draw_all': '-a'}
    RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

    def __init__(self, args: list[str], context):
        context_time = time.time()
        self.context = context
        self.args = args
        self.draw_all = False
        self.style = []
        object_args = self.__set_flagged_options()
        selection = self.__get_objects(object_args)
        self.selected_objects = selection['objects']
        self.drawing_camera = Drawing_camera(selection['camera'], self)
        camera_viewer = Camera_viewer(self.drawing_camera, self)
        self.subjects = camera_viewer.get_subjects(self.selected_objects)
        frame_size = self.drawing_camera.obj.data.ortho_scale
        self.svg_size = format_svg_size(frame_size * 10, frame_size * 10)
        self.svg_factor = frame_size/RENDER_RESOLUTION_X * \
                self.RESOLUTION_FACTOR
        self.svg_styles = [drawing_styles[d_style].name for d_style in 
                self.style]
        print('*** Drawing_context created in', time.time() - context_time)

    def __set_flagged_options(self) -> list[str]:
        """ Set flagged values from args and return remaining args for 
            getting objects """
        self.draw_all = self.FLAGS['draw_all'] in self.args

        options_idx = []
        flagged_args = [arg for arg in self.args if arg.startswith('-')]
        for arg in flagged_args:
            arg_idx = self.args.index(arg)
            options_idx.append(arg_idx)
            self.style += [l for l in arg if l in drawing_styles]

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
        got_objs = bool(objs)
        for ob in selected_objs:
            if not cam and ob.type == 'CAMERA':
                cam = ob
            if not got_objs and is_renderables(ob):
                objs.append(ob)
        return {'objects': objs, 'camera': cam}
