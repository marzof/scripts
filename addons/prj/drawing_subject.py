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
from prj.svg_path import Svg_path
from bpy_extras.object_utils import world_to_camera_view

def reload_linked_object(obj: bpy.types.Object, obj_matrix: 'mathutils.Matrix',
        link: bool = True, relative: bool = False) -> bpy.types.Object:
    """ Delete obj from scene and reload it from its libary 
        with obj_matrix applied """
    obj_name = obj.name
    obj_lib_filepath = obj.library.filepath
    bpy.data.objects.remove(obj)
    with bpy.data.libraries.load(obj_lib_filepath, link=link, 
            relative=relative) as (data_from, data_to):
        data_to.objects.append(obj_name)

    new_obj = data_to.objects[0]
    bpy.context.collection.objects.link(new_obj)
    new_obj.matrix_world = obj_matrix
    return new_obj

class Drawing_subject:
    obj: bpy.types.Object
    drawing_context: 'Drawing_context'
    name: str
    matrix: 'mathutils.Matrix'
    parent: bpy.types.Object
    library: bpy.types.Library
    is_in_front: bool
    is_cut: bool
    is_behind: bool
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: Svg_path

    def __init__(self, instance_obj: 'Instance_object', 
            draw_context: 'Drawing_context', parent: bpy.types.Object = None,
            cutter: bool = False):
        self.obj = instance_obj.obj
        self.name = instance_obj.name
        self.matrix = instance_obj.matrix
        self.parent = parent
        self.library = self.obj.library
        self.drawing_context = draw_context
        self.drawing_camera = draw_context.drawing_camera

        svg_path_args = {'main': True}
        if self.library and self.parent:
            self.obj = reload_linked_object(self.obj, self.matrix)
            svg_path_args['obj'] = self.parent
        self.svg_path = Svg_path(path=self.get_svg_path(**svg_path_args))
        self.svg_path.add_object(self)

        if not cutter:
            visibility_condition = self.__get_condition()
            self.is_in_front = visibility_condition['in_front']
            self.is_cut = visibility_condition['cut']
            self.is_behind = visibility_condition['behind']
        self.collections = [coll.name for coll in self.obj.users_collection \
                if coll is not bpy.context.scene.collection]
        self.obj_evaluated = self.obj.evaluated_get(draw_context.depsgraph)
        self.type = self.obj.type
        self.lineart_source_type = 'OBJECT'
        self.grease_pencil = None

    def __get_condition(self) -> dict[str,bool]:
        """ Return if object is cut, in front or behind the camera"""
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

    def get_svg_path(self, obj: bpy.types.Object = None, main: bool = False, 
            prefix: str = None, suffix: str = None) -> None:
        """ Return the svg filepath with prefix or suffix """
        if not obj:
            obj = self.obj
        path = self.drawing_camera.path
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        svg_path = f"{path}{sep}{pfx}{obj.name}{sfx}.svg"
        return svg_path

    def set_grease_pencil(self, gp: bpy.types.Object) -> None:
        self.grease_pencil = gp

