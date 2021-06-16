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

svgs_data = dict()

## TODO add some type hints and comments
class Svg_path:
    def __new__(cls, *args, **data) -> 'Svg_path':
        path = data['path']
        if path in svgs_data:
            return svgs_data[path]
        return super(Svg_path, cls).__new__(cls)

    def __init__(self, path: str):
        if path not in svgs_data:
            self.path = path
            self.objects = {}
            svgs_data[path] = self

    def add_object(self, obj):
        self.objects[obj] = []

    def add_object_path(self, obj, path):
        self.objects[obj].append(path)
