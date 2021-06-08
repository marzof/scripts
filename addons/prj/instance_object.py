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


class Instance_object:
    def __init__(self, obj: 'bpy.types.Object', matrix: 'mathutils.Matrix'):
        self.obj = obj
        self.matrix = matrix
        self.matrix_repr = [list(rows) for rows in matrix]
        self.name = obj.name

    def __repr__(self):
        return f'{{"object": "{self.name}", "matrix": {self.matrix_repr}}}'

