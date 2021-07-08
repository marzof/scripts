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
from mathutils import Vector
from prj.utils import create_lineart
from prj.drawing_subject import Drawing_subject
from prj.instance_object import Instance_object
import time

def mesh_by_verts(obj_name: str, verts: list[Vector], scene: bpy.types.Scene) \
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
    instance: Instance_object
    subject: Drawing_subject
    modifier: bpy.types.BooleanModifier
    lineart_gp: bpy.types.Object

    def __init__(self, drawing_context: 'Drawing_context'):
        self.drawing_context = drawing_context
        camera = drawing_context.drawing_camera
        cutter_verts = [v + (camera.direction*.01) for v in camera.frame]
        self.obj = mesh_by_verts('cutter', cutter_verts, 
                drawing_context.working_scene)
        self.instance = Instance_object(obj=self.obj, 
                matrix=self.obj.matrix_world)
        self.subject = Drawing_subject(self.instance, drawing_context, 
                cutter=True)
        self.modifier = self.add_boolean_mod()
        self.lineart_gp = create_lineart(source=self.subject, style='p', 
                scene=self.drawing_context.working_scene)
        self.obj.hide_viewport = True

    def add_boolean_mod(self) -> bpy.types.BooleanModifier:
        modifier = self.obj.modifiers.new('Cut', 'BOOLEAN')
        modifier.operation = 'INTERSECT'
        modifier.solver = 'EXACT'
        return modifier

    def link_to_scene(self) -> None:
        bpy.context.collection.objects.link(self.obj)

    def delete(self, remove_lineart_gp: bool) -> None:
        bpy.data.objects.remove(self.obj, do_unlink=True)
        if remove_lineart_gp:
            bpy.data.objects.remove(self.lineart_gp, do_unlink=True)

    def set_source(self, subject: Drawing_subject) -> None:
        self.modifier.object = subject.obj
        ## TODO use variable, not "cut"
        self.lineart_gp.name = f'cut_{subject.obj.name}'
        self.lineart_gp.hide_viewport = False

    def change_solver(self, solver: str) -> None:
        self.modifier.solver = solver

    def reset_solver(self) -> None:
        self.modifier.solver = 'EXACT'
