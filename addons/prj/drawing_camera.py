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
from mathutils import Vector, Matrix
from prj.working_scene import get_render_basepath, get_working_scene
import time

BASE_ROUNDING: int = 6
LIB_PATH = 'lib'
the_drawing_camera = None

def get_drawing_camera(camera: bpy.types.Object = None) -> 'Drawing_camera':
    """ Return the_drawing_camera (create it if necessary) """
    global the_drawing_camera
    if the_drawing_camera:
        #print('drawing_camera already created')
        return the_drawing_camera
    the_drawing_camera = Drawing_camera(camera)
    #print('create drawing_camera')
    return the_drawing_camera

class Drawing_camera:
    obj: bpy.types.Object
    name: str
    path: str
    direction: Vector
    frame: list[Vector]
    frame_origin: Vector
    frame_x_vector: Vector
    frame_y_vector: Vector
    frame_z_start: float
    clip_start: float
    clip_end: float
    matrix: Matrix

    def __init__(self, camera: bpy.types.Object):
        duplicate = camera.copy()
        duplicate.data = duplicate.data.copy()
        self.obj = duplicate
        self.name = camera.name
        working_scene = get_working_scene()
        working_scene.link_object(self.obj)
        working_scene.scene.camera = self.obj
        paths = self.get_path()
        self.path = paths['cam']
        self.lib_path = paths['lib']
        self.direction = camera.matrix_world.to_quaternion() @ \
                Vector((0.0, 0.0, -1.0))
        self.ortho_scale = camera.data.ortho_scale
        self.clip_start = camera.data.clip_start
        self.clip_end = camera.data.clip_end
        self.matrix = camera.matrix_world
        self.local_frame = [v * Vector((1,1,self.clip_start)) 
                for v in camera.data.view_frame()]
        self.frame = [camera.matrix_world @ v for v in self.local_frame]
        self.frame_origin = self.frame[2]
        self.frame_x_vector = self.frame[1] - self.frame[2]
        self.frame_y_vector = self.frame[0] - self.frame[1]
        self.frame_z_start = -camera.data.clip_start

        self.inverse_matrix = Matrix().Scale(-1, 4, (.0,.0,1.0))
    
    def get_path(self) -> str:
        """ Return folder path named after camera (create it if needed) """
        cam_path = os.path.join(get_render_basepath(), self.name)
        lib_path = os.path.join(cam_path, LIB_PATH)
        try:
            os.mkdir(cam_path)
        except OSError:
            print (f'{cam_path} already exists. Going on')
        try:
            os.mkdir(lib_path)
        except OSError:
            print (f'{lib_path} already exists. Going on')
        return {'cam': cam_path, 'lib': lib_path}

    def __get_translate_matrix(self) -> Matrix:
        """ Get matrix for move camera towards his clip_start """
        normal_vector = Vector((0.0, 0.0, -2 * self.clip_start))
        z_scale = round(self.matrix.to_scale().z, BASE_ROUNDING)
        opposite_matrix = Matrix().Scale(z_scale, 4, (.0,.0,1.0))
        base_matrix = self.matrix @ opposite_matrix
        translation = base_matrix.to_quaternion() @ (normal_vector * z_scale)
        return Matrix.Translation(translation)

    def reverse_cam(self, style: str) -> None:
        """ Inverse camera matrix for back views """
        self.obj.matrix_world = (self.__get_translate_matrix() @ \
                self.matrix) @ self.inverse_matrix

    def restore_cam(self) -> None:
        """ Restore orginal camera values """
        #self.obj.data.clip_end = self.clip_end
        self.obj.matrix_world = self.matrix

