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
import bmesh
from prj.drawing_maker import add_line_art_mod, create_grease_pencil
from prj.drawing_maker import GREASE_PENCIL_PREFIX
from prj.working_scene import get_working_scene
from prj.drawing_style import drawing_styles
from prj.utils import remove_grease_pencil, add_modifier
import time

CAMERA_DISTANCE = .0001
CUTTER_NAME = 'cutter'
the_cutter = None

def get_cutter(drawing_context: 'Drawing_context' = None) -> 'Cutter':
    """ Return the_cutter (create it if necessary) """
    global the_cutter
    if not the_cutter:
        the_cutter = Cutter(drawing_context)
        print('create cutter')
        return the_cutter
    print('cutter already created')
    return the_cutter

def mesh_by_verts(obj_name: str, verts: list['Vector'], scene: bpy.types.Scene) \
        -> bpy.types.Object:
    """ Create a mesh object from verts """
    mesh = bpy.data.meshes.new(obj_name)
    obj = bpy.data.objects.new(obj_name, mesh)
    if not scene:
        scene = bpy.context.scene
    scene.collection.objects.link(obj)

    bm = bmesh.new()
    bm.from_object(obj, bpy.context.view_layer.depsgraph)
    for v in verts:
        bm.verts.new(v)

    bmesh.ops.contextual_create(bm, geom=bm.verts)
    bm.to_mesh(mesh)
    bm.free()

    return obj

class Cutter:
    obj: bpy.types.Object
    modifier: bpy.types.BooleanModifier
    lineart_gp: bpy.types.Object

    def __init__(self, drawing_context: 'Drawing_context'):
        self.drawing_context = drawing_context
        self.working_scene = get_working_scene()
        camera = drawing_context.drawing_camera
        cutter_verts = [v + (camera.direction * CAMERA_DISTANCE) \
                for v in camera.frame]
        self.obj = mesh_by_verts(CUTTER_NAME, cutter_verts, 
                self.working_scene.scene)
        self.modifier = add_modifier(self.obj, 'Cut', 'BOOLEAN', 
                {'operation': 'INTERSECT', 'solver': 'EXACT'})
        
        lineart_gp_name = GREASE_PENCIL_PREFIX + self.obj.name
        self.lineart_gp = create_grease_pencil(lineart_gp_name, 
                scene=self.working_scene.scene)
        add_line_art_mod(self.lineart_gp, self.obj, 'OBJECT', 'p', False)
        self.obj.hide_viewport = True
        self.obj.hide_render = True

    def remove(self) -> None:
        self.working_scene.unlink_object(self.obj)
        bpy.data.meshes.remove(self.obj.data)
        remove_grease_pencil(self.lineart_gp)
        self.lineart_gp = None
        global the_cutter
        the_cutter = None

    def set_source(self, subject: 'Drawing_subject') -> None:
        self.modifier.object = subject.obj
        prefix = drawing_styles['c'].name
        self.lineart_gp.name = f'{prefix}_{subject.obj.name}'
        self.lineart_gp.hide_viewport = False
        self.lineart_gp.hide_render = False

    def change_solver(self, solver: str) -> None:
        self.modifier.solver = solver

    def reset_solver(self) -> None:
        self.modifier.solver = 'EXACT'

