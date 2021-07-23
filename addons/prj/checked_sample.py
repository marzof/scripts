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

import inspect
from prj.instance_object import Instance_object, instance_objects

checked_samples: dict[tuple[float], 'Checked_sample'] = dict()
samples_content: dict[tuple, 'Checked_sample'] = dict()

def matrix_to_tuple(matrix) -> tuple[tuple[float]]:
    return tuple([tuple(row) for row in matrix])

class Checked_sample(Instance_object):
    def __new__(cls, *args, **data) -> 'Checked_sample':
        """ Create a new Checked_sample only if data are not yet
            used (and kept in samples_content) """
        if data['matrix']:
            matrix = data['matrix'].copy().freeze()
            content_data = (data['obj'], matrix)
            if content_data in samples_content:
                return samples_content[content_data]
        return super(Checked_sample, cls).__new__(cls)

    def __init__(self, coords: tuple[float], obj: 'bpy.types.Object', 
            matrix: 'mathutils.Matrix', collect: bool=True):
        self.coords = coords
        self.obj = obj
        if obj and obj.library: 
            self.library = obj.library
        else:
            self.library = None
        self.matrix = matrix
        self.matrix_tuple = matrix_to_tuple(matrix) if matrix else None
        self.instance_object = self.get_instance_object()
        self.is_none = self.obj == None
        self.content = self if not coords else Checked_sample(
                coords=None, obj=self.obj, matrix=self.matrix, collect=collect)
        if coords and collect:
            checked_samples[coords] = self
        if matrix and collect:
            samples_content[(obj, matrix.copy().freeze())] = self.content

    def get_instance_object(self):
        if not instance_objects or not self.obj:
            return None
        instance_data = (self.obj, self.library, self.matrix.copy().freeze())
        instance_obj = instance_objects[instance_data]
        ## If called from another file set self.instance_object and return it
        if __file__ != inspect.stack()[1].filename:
            self.instance_object = instance_obj
            return self.instance_object
        ## Otherwise just return it so it's the caller to assign it to 
        ## self.instance_object 
        return instance_obj


    def __repr__(self) -> str:
        obj_name = self.obj.name if self.obj else None
        library_filepath = self.library.filepath if self.library else None
        repr_dict = {"object": obj_name, "library": library_filepath, 
                "matrix": self.matrix_tuple}
        return str(repr_dict)

