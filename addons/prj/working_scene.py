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
import math
from prj.utils import get_resolution

## TODO general data: put in main or __init__
WB_RENDER_FILENAME = 'prj_working_scene.tif'
get_render_basepath = lambda: bpy.path.abspath(bpy.context.scene.render.filepath)

the_working_scene = None

def get_working_scene() -> 'Working_scene':
    global the_working_scene
    if not the_working_scene:
        working_scene = Working_scene()
        the_working_scene = working_scene
        return the_working_scene
    return the_working_scene

## TODO Rename in Drawing_scene
class Working_scene:
    DEFAULT_RESOLUTION_PERCENTAGE: int = 100
    scene: bpy.types.Scene

    def __init__(self, scene_name: str='prj', filename: str=WB_RENDER_FILENAME,
            resolution: list[int] = None, camera: bpy.types.Object= None):
        self.scene = bpy.data.scenes.new(name=scene_name)
        self.scene.render.filepath = get_render_basepath() + filename
        self.scene.render.engine = 'BLENDER_WORKBENCH'
        self.scene.render.resolution_percentage = \
                self.DEFAULT_RESOLUTION_PERCENTAGE
        self.scene.display.render_aa = 'OFF'
        self.scene.display.shading.light = 'FLAT'
        self.scene.display.shading.color_type = 'OBJECT'
        self.scene.display_settings.display_device = 'None'
        self.scene.view_settings.view_transform = 'Standard'
        self.scene.view_settings.look = 'None'
        ## TODO check look, exposure and gamma too
        self.scene.render.film_transparent = True
        self.scene.render.image_settings.file_format = 'TIFF'
        self.scene.render.image_settings.tiff_codec = 'NONE'
        self.scene.render.image_settings.color_mode = 'RGBA'
        if resolution:
            self.scene.render.resolution_x = resolution[0]
            self.scene.render.resolution_y = resolution[1]
        if camera:
            self.link_object(camera)
            self.scene.camera = camera
        self.subjects = []

    def add_subject(self, subject: 'Drawing_subject') -> None:
        self.subjects.append(subject)


    def link_object(self, obj: bpy.types.Object) -> None:
        self.scene.collection.objects.link(obj)

    def unlink_object(self, obj: bpy.types.Object) -> None:
        self.scene.collection.objects.unlink(obj)

    def get_resolution_percentage(self) -> int:
        return self.scene.render.resolution_percentage

    def set_resolution_percentage(self, percentage: int) -> None:
        self.scene.render.resolution_percentage = int(percentage)

    def get_resolution(self) -> list[int]:
        return [self.scene.render.resolution_x, self.scene.render.resolution_y]

    def set_resolution(self, cam_scale: float = None, 
            drawing_scale: float = None, 
            resolution: list[int] = None) -> list[int]:
        if not resolution:
            resolution = get_resolution(cam_scale, drawing_scale)
        self.scene.render.resolution_x = resolution[0]
        self.scene.render.resolution_y = resolution[1]
        return resolution
        
    def remove(self, del_subjs: bool = False, clear: bool = False) -> None:
        """ Unlink every objects in scene, delete them if necessary and remove
            the scene """
        if del_subjs:
            for subj in self.subjects:
                subj.remove()
        for obj in self.scene.collection.all_objects:
            self.scene.collection.objects.unlink(obj)
            if clear:
                bpy.data.objects.remove(obj)
        bpy.data.scenes.remove(self.scene)
        global the_working_scene
        if self == the_working_scene:
            the_working_scene = None
