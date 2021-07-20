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
from mathutils import Vector

import time

class Scanner:
    depsgraph: bpy.types.Depsgraph
    target = bpy.types.Object
    target_found = bool

    def __init__(self, depsgraph: bpy.types.Depsgraph, 
            draw_camera: 'Drawing_camera', step: float = 1.0):
        self.depsgraph = depsgraph
        self.draw_camera = draw_camera
        self.step = step
        self.target = None
        self.target_found = None

    def get_step(self) -> float:
        return self.step

    def set_step(self, step:float) -> None:
        self.step = step

    def __get_ray_origin(self, v: tuple[float], camera: 'Drawing_camera') -> \
            Vector:
        """ Get frame point moving origin in x and y direction by v factors"""
        x_coord = camera.frame_origin + (camera.frame_x_vector * v[0])
        coord = x_coord + (camera.frame_y_vector * v[1])
        return Vector(coord)
    
    def scan_area_for_target(self, area_samples: list[tuple[float]], 
            camera: 'Drawing_camera', target: bpy.types.Object = None) -> dict:
        """ Scan area by its sample and return if target is found 
            and scan_result """
        self.target = target
        scan_result = self.scan_area(area_samples, camera)
        target_found = self.target_found
        ## Reset target values
        self.target = None
        self.target_found = None
        return {'result': target_found, 'samples': scan_result}

    def scan_area(self, area_samples: list[tuple[float]], 
            camera: 'Drawing_camera') -> dict[tuple[float], dict]:
        """ Scan area by its samples and return checked_samples maps """
        print("Start scan...")
        scanning_start_time = time.time()

        checked_samples = {}
        print('total area to scan', len(area_samples))
        for sample in area_samples:
            checked_samples[sample] = None
            ray_origin = self.__get_ray_origin(sample, self.draw_camera)
            res, loc, nor, ind, obj, mat = bpy.context.scene.ray_cast(
                self.depsgraph, ray_origin, camera.direction)
            if not obj:
                continue
            if self.target and obj == self.target:
                scanning_time = time.time() - scanning_start_time
                print(f"   ...scanned in {scanning_time} seconds")
                self.target_found = True
                return checked_samples
            checked_samples[sample] = {'result': res, 'location': loc,
                    'normal': nor, 'index': ind, 'object': obj, 'matrix': mat}
        if self.target:
            scanning_time = time.time() - scanning_start_time
            print(f"   ...scanned in {scanning_time} seconds")
            self.target_found = False
            return checked_samples
        scanning_time = time.time() - scanning_start_time
        print(f"   ...scanned in {scanning_time} seconds")
        return checked_samples

