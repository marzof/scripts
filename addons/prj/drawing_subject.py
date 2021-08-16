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
import math
from mathutils import Vector
from prj.utils import point_in_quad, linked_obj_to_real
from prj.svg_path import Svg_path
from prj.working_scene import get_working_scene
from bpy_extras.object_utils import world_to_camera_view

libraries = []

def to_hex(c: float) -> str:
    """ Return srgb hexadecimal version of c """
    if c < 0.0031308:
        srgb = 0.0 if c < 0.0 else c * 12.92
    else:
        srgb = 1.055 * math.pow(c, 1.0 / 2.4) - 0.055
    return hex(max(min(int(srgb * 255 + 0.5), 255), 0))

def make_linked_object_real(obj: bpy.types.Object, 
        obj_matrix: 'mathutils.Matrix', scene: bpy.types.Scene, 
        parent: bpy.types.Object, link: bool = True, relative: bool = False) \
                -> bpy.types.Object:
    """ Make linked obj real and put it into scene with obj_matrix applied """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    if not scene:
        scene = bpy.context.scene
    print('make real', obj)
    obj_name = obj.name
    if parent:
        new_obj_name = f"{parent.name}_{obj.name}"

    if obj.library:
        new_obj = linked_obj_to_real(obj, link, relative)
        new_obj.name = new_obj_name
    else:
        eval_obj = obj.evaluated_get(depsgraph)
        new_mesh = bpy.data.meshes.new_from_object(eval_obj)
        new_obj = bpy.data.objects.new(new_obj_name, new_mesh)

    new_obj.data.materials.clear()
    scene.collection.objects.link(new_obj)
    new_obj.matrix_world = obj_matrix
    return new_obj

def frame_obj_bound_rect(cam_bound_box: list[Vector]) -> dict[str, float]:
    """ Get the bounding rect of obj in cam view coords  """
    bbox_xs = [v.x for v in cam_bound_box]
    bbox_ys = [v.y for v in cam_bound_box]
    bbox_zs = [v.z for v in cam_bound_box]
    x_min, x_max = max(0.0, min(bbox_xs)), min(1.0, max(bbox_xs))
    y_min, y_max = max(0.0, min(bbox_ys)), min(1.0, max(bbox_ys))
    if x_min > 1 or x_max < 0 or y_min > 1 or y_max < 0:
        ## obj is out of frame
        return None
    return {'x_min': x_min, 'y_min': y_min, 'x_max': x_max, 'y_max': y_max}

class Drawing_subject:
    obj: bpy.types.Object
    drawing_context: 'Drawing_context'
    name: str
    bounding_rect: list[Vector]
    overlapping_objects: list['Drawing_subject']
    matrix: 'mathutils.Matrix'
    parent: bpy.types.Object
    library: bpy.types.Library
    cam_bound_box: list[Vector]
    is_in_front: bool
    is_cut: bool
    is_behind: bool
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: Svg_path

    def __init__(self, instance_obj: 'Instance_object', 
            draw_context: 'Drawing_context', is_cutter: bool = False):
        print('Create subject for', instance_obj.name)
        self.instance = instance_obj.instance
        self.instance_obj = instance_obj
        self.name = instance_obj.name
        self.matrix = instance_obj.matrix
        self.parent = instance_obj.parent
        self.is_instance = instance_obj.is_instance
        self.library = instance_obj.library
        self.cam_bound_box = instance_obj.cam_bound_box
        if self.library and self.library not in libraries:
            libraries.append(self.library)
        self.drawing_context = draw_context
        self.drawing_camera = draw_context.drawing_camera
        self.overlapping_objects = []
        self.bounding_rect = []

        svg_path_args = {'main': True}
        working_scene = get_working_scene()
        if not is_cutter and self.is_instance:
            self.obj = make_linked_object_real(instance_obj.obj, self.matrix, 
                    working_scene, self.parent)
        elif instance_obj.name not in working_scene.objects:
            ## Move a no-materials duplicate to working_scene: materials could 
            ## bother lineart (and originals are kept untouched)
            if instance_obj.obj.type == 'CURVE':
                ## If a bevel object is applied to the curve, need to restate it
                curve_bevel_obj = instance_obj.instance.data.bevel_object
                if curve_bevel_obj:
                    bpy.data.objects[self.name].data.bevel_object = \
                            bpy.data.objects[curve_bevel_obj.name]
                    depsgraph = bpy.context.evaluated_depsgraph_get()
                ## TODO Delete commented lines after test with curve instances
                #mesh = bpy.data.meshes.new_from_object(instance_obj.instance)
                #mesh_obj = bpy.data.objects.new(name=self.name, object_data=mesh)
                #mesh_obj.matrix_world = self.matrix
                #self.obj = mesh_obj
            #else:
                #duplicate = instance_obj.obj.copy()
                #duplicate.data = duplicate.data.copy()
                #duplicate.data.materials.clear()
                #self.obj = duplicate
            mesh = bpy.data.meshes.new_from_object(instance_obj.instance)
            mesh_obj = bpy.data.objects.new(name=self.name, object_data=mesh)
            mesh_obj.matrix_world = self.matrix
            mesh_obj.data.materials.clear()
            self.obj = mesh_obj
            working_scene.collection.objects.link(self.obj)

        self.svg_path = Svg_path(path=self.get_svg_path(**svg_path_args))
        self.svg_path.add_object(self)

        if not is_cutter:
            self.is_in_front = instance_obj.is_in_front
            self.is_behind = instance_obj.is_behind
            self.is_cut = self.is_in_front and self.is_behind
        self.collections = [coll.name for coll in self.obj.users_collection \
                if coll is not bpy.context.scene.collection]
        self.type = self.obj.type
        self.lineart_source_type = 'OBJECT'
        self.grease_pencil = None

    def set_color(self, rgba: tuple[float]) -> None:
        r, g, b, a = rgba
        self.obj.color = rgba
        self.color = (int(to_hex(r),0), int(to_hex(g),0), int(to_hex(b),0),
                int(to_hex(a),0))

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
    
    def get_bounding_rect(self) -> None:
        bounding_rect = frame_obj_bound_rect(self.cam_bound_box)
        verts = [Vector((bounding_rect['x_min'], bounding_rect['y_min'])),
                Vector((bounding_rect['x_max'], bounding_rect['y_min'])),
                Vector((bounding_rect['x_max'], bounding_rect['y_max'])),
                Vector((bounding_rect['x_min'], bounding_rect['y_max']))]
        self.bounding_rect = verts

    def add_overlapping_obj(self, subject: 'Drawing_subject') -> None:
        if subject not in self.overlapping_objects:
            self.overlapping_objects.append(subject)

    def get_overlap_subjects(self, subjects: list['Drawing_subject']) -> None:
        for subject in subjects:
            if subject == self:
                continue
            for vert in self.bounding_rect:
                if point_in_quad(vert, subject.bounding_rect):
                    self.overlapping_objects.append(subject)
                    subject.add_overlapping_obj(self)
                    break

    def remove(self):
        working_scene = get_working_scene()
        working_scene.collection.objects.unlink(self.obj)
        bpy.data.objects.remove(self.obj, do_unlink=True)

