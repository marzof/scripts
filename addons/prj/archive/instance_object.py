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

instance_objects = dict()

class Instance_object:
    def __new__(cls, *args, **data) -> 'Instance_object':
        """ Create a new Instance_object only if data are not yet
            used (and kept in instance_objects) """
        if data:
            matrix = data['matrix'].copy().freeze()
            instance_data = (data['obj'], data['library'], matrix)
            if instance_data in instance_objects:
                return instance_objects[instance_data] 
        return super(Instance_object, cls).__new__(cls)

    def __init__(self, instance: 'bpy.types.DepsgraphObjectInstance', 
            obj: 'bpy.types.Object', library: 'bpy.types.Library', 
            is_instance: bool, parent: 'bpy.types.Object', in_front: bool,
            behind:bool, cam_bound_box: list['Vector'], mesh: 'bpy.types.Mesh',
            matrix: 'mathutils.Matrix'):
        if self not in instance_objects.values():
            self.instance = instance
            self.obj = obj
            self.mesh = mesh
            self.name = self.obj.name
            self.library = library
            self.is_instance = is_instance
            self.parent = parent
            self.matrix = matrix.copy().freeze()
            self.is_in_front = in_front
            self.is_behind = behind
            self.cam_bound_box = cam_bound_box
            instance_objects[(self.obj, self.library, self.matrix)] = self

    def is_same_content_as(self, content: 'Instance_object') -> bool:
        """ Check if self and content have the same content """
        if not content:
            return False
        return self.obj == content.obj and self.matrix == content.matrix

    def __repr__(self) -> str:
        parent_name = None if not self.parent else self.parent.name
        repr_dict = {"object": self.name, "library": self.library, 
                "is_instance": self.is_instance, "parent": parent_name, 
                #"matrix": self.matrix,
                }
        return str(repr_dict)

