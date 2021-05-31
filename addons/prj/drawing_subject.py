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
import os
from prj.utils import get_obj_bound_box
from bpy_extras.object_utils import world_to_camera_view

class Drawing_subject:
    obj: bpy.types.Object
    drawing_context: 'Drawing_context'
    is_in_front: bool
    is_cut: bool
    is_behind: bool
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: str

    def __init__(self, obj, draw_context):
        self.obj = obj
        if (type(obj) == bpy.types.Object and obj.type == 'EMPTY'):
            self.obj = prj_utils.make_local_collection(self.obj)
        self.name = obj.name
        self.drawing_context = draw_context
        self.drawing_camera = draw_context.drawing_camera
        condition = self.__get_condition()
        self.is_in_front = condition['in_front']
        self.is_cut = condition['cut']
        self.is_behind = condition['behind']
        self.collections = [coll.name for coll in obj.users_collection]

        if type(self.obj) == bpy.types.Collection:
            self.type = 'COLLECTION'
            self.lineart_source_type = self.type
            self.objects = self.obj.all_objects
        else:
            self.type = obj.type
            self.lineart_source_type = 'OBJECT'
            self.objects = [obj]

        self.lineart_source = self.obj
        self.grease_pencil = None

    def __get_condition(self):
        world_obj_bbox = get_obj_bound_box(self.obj, 
                self.drawing_context.depsgraph)
        bbox_from_cam_view = [world_to_camera_view(bpy.context.scene, 
            self.drawing_camera.obj, v) for v in world_obj_bbox]
        zs = [v.z for v in bbox_from_cam_view]
        z_min, z_max = min(zs), max(zs)
        cut_plane = self.drawing_camera.clip_start
        return {'cut': z_min <= cut_plane <= z_max,
                'in_front': cut_plane < z_max,
                'behind': z_min < cut_plane
                }

    def set_drawing_context(self, draw_context: 'Drawing_context') -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> 'Drawing_context':
        return self.drawing_context

    def get_svg_path(self, prefix = None, suffix = None) -> str:
        """ Return the svg filepath with prefix or suffix """
        path = self.drawing_camera.path
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        self.svg_path = f"{path}{sep}{pfx}{self.obj.name}{sfx}.svg"
        return self.svg_path

    def set_grease_pencil(self, gp: bpy.types.Object) -> None:
        self.grease_pencil = gp

