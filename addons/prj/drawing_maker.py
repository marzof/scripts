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
import prj
from prj.utils import make_active
from prj.drawing_subject import Drawing_subject

def add_line_art_mod(gp: bpy.types.Object, source: bpy.types.Object, 
        source_type: str, style: str) -> None:
    """ Add a line art modifier to gp from source of the source_type 
    with style """

    gp_layer = gp.data.layers.new(prj.STYLES[style]['name'])
    gp_layer.frames.new(1)
    gp_mat_name = prj.GREASE_PENCIL_MAT + '_' + prj.STYLES[style]['name']
    if gp_mat_name not in bpy.data.materials:
        gp_mat = bpy.data.materials.new(gp_mat_name)
    else:
        gp_mat = bpy.data.materials[gp_mat_name]
    if not gp_mat.is_grease_pencil:
        bpy.data.materials.create_gpencil_data(gp_mat)
    gp.data.materials.append(gp_mat)

    ## Create and setup lineart modifier
    gp_mod_name = prj.GREASE_PENCIL_MOD + '_' + prj.STYLES[style]['name']
    gp.grease_pencil_modifiers.new(gp_mod_name, 'GP_LINEART')
    gp_mod = gp.grease_pencil_modifiers[gp_mod_name]
    gp_mod.target_layer = gp_layer.info
    gp_mod.target_material = gp_mat
    gp_mod.chaining_image_threshold = prj.STYLES[style]['chaining_threshold']
    gp_mod.use_multiple_levels = True
    gp_mod.level_start = prj.STYLES[style]['occlusion_start']
    gp_mod.level_end = prj.STYLES[style]['occlusion_end']
    gp_mod.source_type = source_type
    print('lineart source is', source)
    if source_type == 'OBJECT':
        gp_mod.source_object = source
    elif source_type == 'COLLECTION':
        gp_mod.source_collection = source

def create_grease_pencil(name: str) -> bpy.types.Object:
    """ Create a grease pencil """
    gp = bpy.data.grease_pencils.new(name)

    gp_layer = gp.layers.new(prj.GREASE_PENCIL_LAYER)
    gp_layer.frames.new(1)
    
    gp_mat = bpy.data.materials.new(prj.GREASE_PENCIL_MAT)
    bpy.data.materials.create_gpencil_data(gp_mat)
    gp.materials.append(gp_mat)

    obj = bpy.data.objects.new(name, gp)
    bpy.context.collection.objects.link(obj)
    return obj

def create_lineart(source: Drawing_subject, style: str) -> bpy.types.Object:
    """ Create source.grease_pencil if needed and add a lineart modifier 
    with style to it """
    if not source.grease_pencil:
        source.set_grease_pencil(create_grease_pencil(
                prj.GREASE_PENCIL_PREFIX + source.obj.name))
    add_line_art_mod(source.grease_pencil, source.obj, 
            source.lineart_source_type, style)
    return source.grease_pencil

class Drawing_maker:
    drawing_context: 'Drawing_context'
    drawing_camera: 'Drawing_camera'

    def __init__(self, draw_context):
        self.drawing_context = draw_context
        self.drawing_camera = draw_context.drawing_camera

    def set_drawing_context(self, draw_context: 'Drawing_context') -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> 'Drawing_context':
        return self.drawing_context
    
    def export_grease_pencil(self, grease_pencil: bpy.types.Object, 
            remove: bool, svg_suffix: str = '') -> str:
        """ Export grease_pencil to svg and return its path """
        make_active(grease_pencil)

        svg_path = self.subject.get_svg_path(suffix=svg_suffix)
        bpy.ops.wm.gpencil_export_svg(filepath=svg_path, 
                selected_object_type='VISIBLE')
        if remove:
            bpy.data.objects.remove(grease_pencil, do_unlink=True)
            self.subject.set_grease_pencil(None)
        return svg_path

    def __create_lineart_grease_pencil(self, drawing_style: str) \
            -> bpy.types.Object:
        """ Create a grease pencil with lineart modifier according to 
            drawing_style """
        if not self.subject: return None
        lineart_gp = create_lineart(source=self.subject, style=drawing_style)
        return lineart_gp

    def draw(self, subject: Drawing_subject, styles: str, 
            remove: bool = True) -> list[str]:
        """ Create a grease pencil for subject and add a lineart modifier for
            every draw_style. 
            Then export the grease pencil and return its filepath """
        self.subject = subject
        styles_to_process = [s for s in styles if 
                    getattr(subject, prj.STYLES[s]['condition'])]
        for draw_style in styles_to_process:
            print('draw', subject.name, 'in style', draw_style)
            file_suffix = prj.STYLES[draw_style]['name']
            self.drawing_camera.set_cam_for_style(draw_style)
            lineart_gp = self.__create_lineart_grease_pencil(draw_style)
            if not lineart_gp: 
                continue
            self.export_grease_pencil(lineart_gp, remove, file_suffix)
            self.drawing_camera.restore_cam()

