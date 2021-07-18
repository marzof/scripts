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
        instance_data = (data['obj'], data['library'])
        if instance_data in instance_objects:
            return instance_objects[instance_data] 
        return super(Instance_object, cls).__new__(cls)

    def __init__(self, obj: 'bpy.types.Object', library: str, is_instance: bool,
            parent: 'bpy.types.Object', matrix: 'mathutils.Matrix'):
        if self not in instance_objects.values():
            self.obj = obj
            self.name = self.obj.name
            self.library = library
            self.is_instance = is_instance
            self.parent = parent
            self.matrix = matrix
            instance_objects[(obj, library)] = self

    def __repr__(self) -> str:
        parent_name = None if not self.parent else self.parent.name
        repr_dict = {"object": self.name, "library": self.library, 
                "is_instance": self.is_instance, "parent": parent_name}
        return str(repr_dict)

