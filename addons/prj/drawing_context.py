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
from prj.drawing_subject import reset_subjects_list
from prj.working_scene import get_working_scene
from prj.svg_path import reset_svgs_data
from prj.cutter import get_cutter
from prj.utils import get_scene_tree, get_resolution, MIN_UNIT_FRACTION, flatten
from prj.utils import name_cleaner, check_obj_name_uniqueness
import time

is_renderables = lambda obj: (obj.type, bool(obj.instance_collection)) \
        in [('MESH', False), ('CURVE', False), ('EMPTY', True)]
format_svg_size = lambda x, y: (str(x) + 'mm', str(y) + 'mm')
the_drawing_context = None

def get_drawing_context(args: list[str] = None) -> 'Drawing_context':
    """ Return the_drawing_context (create it if necessary) """
    global the_drawing_context
    if the_drawing_context:
        return the_drawing_context
    the_drawing_context = Drawing_context(args)
    if not the_drawing_context.drawing_camera:
        return
    print('create drawing_context')
    return the_drawing_context

class Drawing_context:
    args: list[str]
    draw_all: bool
    xray_drawing: bool
    back_drawing: bool
    draw_outline: bool
    wire_drawing: bool
    drawing_scale: float
    selected_objects: list[bpy.types.Object]
    subjects: list['Drawing_subject']
    cutter: 'Cutter'
    drawing_camera: 'Drawing_camera'
    scene_tree: dict[tuple[int], bpy.types.Collection]
            # or dict[tuple[int], bpy.types.Object]

    FLAGS: dict[str, str] = {'draw_all': '-a', 'drawing_scale': '-s',
            'draw_outline': '-o', 'xray_drawing': '-x', 'back_drawing': '-b',
            'wire_drawing': '-w', 'reset_options': '-r'}
    RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

    def __init__(self, args: list[str]):
        context_time = time.time()
        self.args = args
        self.draw_all = False
        self.xray_drawing = False
        self.back_drawing = False
        self.draw_outline = False
        self.wire_drawing = False
        self.reset_option = False
        self.drawing_scale = None
        object_args = self.__set_flagged_options()
        selection = self.__get_objects(object_args)
        self.selected_objects = selection['objects']
        camera = selection['camera']
        if not camera:
            print("\nJust one camera has to be selected")
            self.drawing_camera = None
            return
        self.render_resolution = get_resolution(camera.data,
                bpy.context.scene, self.drawing_scale)
        self.working_scene = get_working_scene()
        self.working_scene.set_resolution(resolution=self.render_resolution)
        self.drawing_camera = get_drawing_camera(camera) 
        self.scene_tree = get_scene_tree(bpy.context.scene.collection)

        self.subjects = get_subjects(self.selected_objects, self)
        self.all_subjects = list(set(flatten(self.subjects.values())))
        self.cutter = get_cutter(self)
        self.svg_size = format_svg_size(
                self.render_resolution[0] / MIN_UNIT_FRACTION,
                self.render_resolution[1] / MIN_UNIT_FRACTION)
        self.svg_factor = self.RESOLUTION_FACTOR / (10 * MIN_UNIT_FRACTION)
        print('*** Drawing_context created in', time.time() - context_time)

    def __set_flagged_options(self) -> list[str]:
        """ Set flagged values from args and return remaining args for 
            getting objects """
        self.reset_option = self.FLAGS['reset_options'] in self.args
        self.back_drawing = self.FLAGS['back_drawing'] in self.args
        self.draw_outline = self.FLAGS['draw_outline'] in self.args
        self.draw_all = False if self.back_drawing else \
                self.FLAGS['draw_all'] in self.args
        self.xray_drawing = True if self.back_drawing else \
                self.FLAGS['xray_drawing'] in self.args
        self.wire_drawing = False if self.draw_outline else \
                self.FLAGS['wire_drawing'] in self.args

        if self.FLAGS['drawing_scale'] not in self.args:
            print('Please set a scale for the drawing')
            raise Exception('DRAWING SCALE MISSING')
        
        drawing_scale_idx = self.args.index(self.FLAGS['drawing_scale']) + 1
        self.drawing_scale = float(self.args[drawing_scale_idx])

        object_args = [arg for idx, arg in enumerate(self.args) \
                if not arg.startswith('-') and idx != drawing_scale_idx]

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
    
    def remove(self) -> None:
        global the_drawing_context
        the_drawing_context = None
        self.drawing_camera.remove()
        self.cutter.remove()
        reset_svgs_data()
        reset_subjects_list()
        self.working_scene.remove(del_subjs=True, clear=True)
