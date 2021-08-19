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

## TODO general data: put in main or __init__ and handle render resolution
##      based on scale of drawing (level of detail)
RENDER_BASEPATH = bpy.path.abspath(bpy.context.scene.render.filepath)
RENDER_RESOLUTION_X = bpy.context.scene.render.resolution_x
RENDER_RESOLUTION_Y = bpy.context.scene.render.resolution_y

WB_RENDER_FILENAME = 'prj_working_scene.tif'
the_working_scene = None

def get_working_scene() -> 'Working_scene':
    global the_working_scene
    if not the_working_scene:
        working_scene = Working_scene()
        the_working_scene = working_scene.scene
        return the_working_scene
    return the_working_scene

class Working_scene:
    RENDER_BASEPATH: str
    RENDER_RESOLUTION_X: int
    RENDER_RESOLUTION_Y: int
    scene: bpy.types.Scene

    def __init__(self):
        self.scene = bpy.data.scenes.new(name='prj')
        self.scene.render.resolution_x = RENDER_RESOLUTION_X
        self.scene.render.resolution_y = RENDER_RESOLUTION_Y
        self.scene.render.filepath = RENDER_BASEPATH + WB_RENDER_FILENAME
        self.scene.render.engine = 'BLENDER_WORKBENCH'
        self.scene.display.render_aa = 'OFF'
        self.scene.display.shading.light = 'FLAT'
        self.scene.display.shading.color_type = 'OBJECT'
        self.scene.display_settings.display_device = 'sRGB'
        self.scene.view_settings.view_transform = 'Standard'
        ## TODO check look, exposure and gamma too
        self.scene.render.film_transparent = True
        self.scene.render.image_settings.file_format = 'TIFF'
        self.scene.render.image_settings.tiff_codec = 'NONE'
        self.scene.render.image_settings.color_mode = 'RGBA'
        ## TODO change rendering filepath
        #self.scene.render.filepath = '/home/mf/Documents/test.tif'

