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
from prj.drawing_camera import get_drawing_camera
from prj.subject_finder import get_subjects
from prj.drawing_style import drawing_styles
from prj.working_scene import get_working_scene
import time

is_renderables = lambda obj: (obj.type, bool(obj.instance_collection)) \
        in [('MESH', False), ('CURVE', False), ('EMPTY', True)]
format_svg_size = lambda x, y: (str(x) + 'mm', str(y) + 'mm')
the_drawing_context = None

def get_drawing_context(args: list[str] = None):
    """ Return the_drawing_context (create it if necessary) """
    global the_drawing_context
    if the_drawing_context:
        print('drawing_context already created')
        return the_drawing_context
    the_drawing_context = Drawing_context(args)
    print('create drawing_context')
    return the_drawing_context

class Drawing_context:
    args: list[str]
    draw_all: bool
    drawing_scale: float
    style: list[str]
    selected_objects: list[bpy.types.Object]
    subjects: list['Drawing_subject']
    drawing_camera: 'Drawing_camera'

    DEFAULT_STYLES: list[str] = ['p', 'c']
    FLAGS: dict[str, str] = {'draw_all': '-a', 'drawing_scale': '-s'}
    RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch
    RENDER_FACTOR: int = 4

    def __init__(self, args: list[str]):
        context_time = time.time()
        self.args = args
        self.draw_all = False
        self.drawing_scale = None
        self.style = []
        object_args = self.__set_flagged_options()
        selection = self.__get_objects(object_args)
        self.selected_objects = selection['objects']
        self.drawing_camera = get_drawing_camera(selection['camera']) 
        frame_size = self.drawing_camera.ortho_scale
        working_scene = get_working_scene()
        render_resolution = working_scene.set_resolution(frame_size, 
                self.drawing_scale * self.RENDER_FACTOR)
        self.subjects = get_subjects(self.selected_objects, self.drawing_scale)
        self.svg_size = format_svg_size(frame_size * self.drawing_scale * 1000, 
            frame_size * self.drawing_scale * 1000)
        self.svg_factor = frame_size * self.drawing_scale * 100 * \
                self.RESOLUTION_FACTOR / render_resolution
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
            if arg == self.FLAGS['drawing_scale']:
                drawing_scale = self.args[arg_idx + 1]
                self.drawing_scale = float(drawing_scale)
                options_idx.append(arg_idx + 1)
                continue
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
        selected_objs = bpy.context.selected_objects
        cam = None
        objs = []
        for ob in args_objs:
            if ob and bpy.data.objects[ob].type == 'CAMERA':
                cam = bpy.data.objects[ob]
            elif ob and is_renderables(bpy.data.objects[ob]) \
                    and not self.draw_all:
                objs.append(bpy.data.objects[ob])
        got_objs = bool(objs)
        for ob in selected_objs:
            if not cam and ob.type == 'CAMERA':
                cam = ob
            if not got_objs and is_renderables(ob) and not self.draw_all:
                objs.append(ob)
        if len(objs) == 0:
            self.draw_all = True
        return {'objects': objs, 'camera': cam}
