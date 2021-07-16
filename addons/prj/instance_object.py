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

def matrix_to_tuple(matrix) -> tuple[tuple[float]]:
    return tuple([tuple(row) for row in matrix])

class Instance_object:
    def __new__(cls, *args, **data) -> 'Instance_object':
        """ Create a new Instance_object only if data are not yet
            used (and kept in instance_objects) """
        instance_data = (data['obj'], matrix_to_tuple(data['matrix']))
        if instance_data in instance_objects:
            return instance_objects[instance_data] 
        return super(Instance_object, cls).__new__(cls)

    def __init__(self, obj: 'bpy.types.Object', matrix: 'mathutils.Matrix'):
        if self not in instance_objects.values():
            self.obj = obj
            self.matrix = matrix.copy()
            self.matrix_repr = [list(rows) for rows in self.matrix]
            self.name = self.obj.name
            self.is_instance = False
            self.parent = None
            instance_objects[(obj, matrix_to_tuple(matrix))] = self

    def __repr__(self) -> str:
        parent_name = None if not self.parent else self.parent.name
        repr_dict = {"object": self.name, "is_instance": self.is_instance,
                "parent": parent_name, "matrix": self.matrix_repr}
        return str(repr_dict)

    def add_instance_data(self, is_instance: bool, 
            parent: 'bpy.types.Object') -> None:
        self.is_instance = is_instance
        self.parent = parent

