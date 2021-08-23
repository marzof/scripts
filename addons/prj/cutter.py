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
from prj.utils import create_grease_pencil, add_line_art_mod
from prj.utils import GREASE_PENCIL_PREFIX
from prj.working_scene import get_working_scene
from prj.drawing_style import drawing_styles
import time

CAMERA_DISTANCE = .0001
CUTTER_NAME = 'cutter'
the_cutter = None

def get_cutter(drawing_context: 'Drawing_context') -> 'Cutter':
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
        working_scene = get_working_scene().scene
        camera = drawing_context.drawing_camera
        cutter_verts = [v + (camera.direction * CAMERA_DISTANCE) \
                for v in camera.frame]
        self.obj = mesh_by_verts(CUTTER_NAME, cutter_verts, working_scene)
        self.modifier = self.add_boolean_mod()
        
        self.lineart_gp = create_grease_pencil(
                GREASE_PENCIL_PREFIX + self.obj.name, scene=working_scene)
        add_line_art_mod(self.lineart_gp, self.obj, 'OBJECT', 'p')
        self.obj.hide_viewport = True
        self.obj.hide_render = True

    def add_boolean_mod(self) -> bpy.types.BooleanModifier:
        """ Assign boolean modifier to self.obj and return it """
        modifier = self.obj.modifiers.new('Cut', 'BOOLEAN')
        modifier.operation = 'INTERSECT'
        modifier.solver = 'EXACT'
        return modifier

    def delete(self, remove_lineart_gp: bool) -> None:
        bpy.data.objects.remove(self.obj, do_unlink=True)
        if remove_lineart_gp:
            bpy.data.objects.remove(self.lineart_gp, do_unlink=True)

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

