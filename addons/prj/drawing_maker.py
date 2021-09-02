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
from prj.utils import make_active
from prj.drawing_style import drawing_styles
from prj.drawing_camera import get_drawing_camera
from prj.working_scene import get_working_scene

GREASE_PENCIL_PREFIX = 'prj_'
GREASE_PENCIL_LAYER = 'prj_lay'
GREASE_PENCIL_MAT = 'prj_mat'
GREASE_PENCIL_MOD = 'prj_la'

def add_line_art_mod(gp: bpy.types.Object, source: bpy.types.Object, 
        source_type: str, style: str) -> None:
    """ Add a line art modifier to gp from source of the source_type 
    with style """

    gp_layer = gp.data.layers.new(drawing_styles[style].name)
    gp_layer.frames.new(1)
    gp_mat_name = GREASE_PENCIL_MAT + '_' + drawing_styles[style].name
    if gp_mat_name not in bpy.data.materials:
        gp_mat = bpy.data.materials.new(gp_mat_name)
    else:
        gp_mat = bpy.data.materials[gp_mat_name]
    if not gp_mat.is_grease_pencil:
        bpy.data.materials.create_gpencil_data(gp_mat)
    gp.data.materials.append(gp_mat)

    ## Create and setup lineart modifier
    gp_mod_name = GREASE_PENCIL_MOD + '_' + drawing_styles[style].name
    gp.grease_pencil_modifiers.new(gp_mod_name, 'GP_LINEART')
    gp_mod = gp.grease_pencil_modifiers[gp_mod_name]
    gp_mod.target_layer = gp_layer.info
    gp_mod.target_material = gp_mat
    gp_mod.chaining_image_threshold = drawing_styles[style].chaining_threshold
    gp_mod.use_multiple_levels = True
    gp_mod.use_remove_doubles = True
    gp_mod.use_clip_plane_boundaries = False
    gp_mod.level_start = drawing_styles[style].occlusion_start
    gp_mod.level_end = drawing_styles[style].occlusion_end
    gp_mod.source_type = source_type
    if source_type == 'OBJECT':
        gp_mod.source_object = source
    elif source_type == 'COLLECTION':
        gp_mod.source_collection = source


def create_grease_pencil(name: str, scene: bpy.types.Scene) -> bpy.types.Object:
    """ Create a grease pencil """
    gp = bpy.data.grease_pencils.new(name)

    gp_layer = gp.layers.new(GREASE_PENCIL_LAYER)
    gp_layer.frames.new(1)
    
    gp_mat = bpy.data.materials.new(GREASE_PENCIL_MAT)
    bpy.data.materials.create_gpencil_data(gp_mat)
    gp.materials.append(gp_mat)

    obj = bpy.data.objects.new(name, gp)
    scene.collection.objects.link(obj)
    return obj

def create_lineart(source: 'Drawing_subject', style: str, 
        scene: bpy.types.Scene, cutter: 'Cutter') -> bpy.types.Object:
    """ Create source.grease_pencil if needed and add a lineart modifier 
        with style to it """
    if style == 'c':
        source.obj.hide_viewport = True 
        return cutter.lineart_gp
    elif style == 'b':
        camera = get_drawing_camera()
        camera.reverse_cam()

    if not scene:
        scene = bpy.context.scene
    if not source.grease_pencil:
        source.set_grease_pencil(create_grease_pencil(
                GREASE_PENCIL_PREFIX + source.obj.name, scene))
    add_line_art_mod(source.grease_pencil, source.obj, 
            source.lineart_source_type, style)
    return source.grease_pencil

def export_grease_pencil(subject: 'Drawing_subject', 
        grease_pencil: bpy.types.Object, 
        remove: bool, svg_suffix: str = '') -> str:
    """ Export grease_pencil to svg and return its path """
    make_active(grease_pencil)

    svg_path = subject.get_svg_path(suffix=svg_suffix)
    
    svg_main_path = subject.svg_path
    svg_main_path.add_object_path(subject, svg_path, svg_suffix)

    bpy.ops.wm.gpencil_export_svg(filepath=svg_path, 
            selected_object_type='VISIBLE') # use_clip_camera=True causes error
    if remove:
        bpy.data.objects.remove(grease_pencil, do_unlink=True)
        subject.set_grease_pencil(None)
    return svg_path

def draw(subject: 'Drawing_subject', styles: str, cutter: 'Cutter',
        remove: bool = True) -> list[str]:
    """ Create a grease pencil for subject (and add a lineart modifier) for
        every draw_style. Then export the grease pencil """
    cutter.set_source(subject)
    drawing_camera = get_drawing_camera()

    ## If cutter doesn't work switch boolean modifier to FAST solver
    if subject.is_cut:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        ###depsgraph.update()
        evaluated_cutter = cutter.obj.evaluated_get(depsgraph)
        if not list(evaluated_cutter.data.vertices):
            cutter.change_solver('FAST')

    styles_to_process = [s for s in styles if 
                getattr(subject, drawing_styles[s].condition)]
    for draw_style in styles_to_process:
        #print('draw', subject.name, 'in style', draw_style)
        remove = draw_style != 'c'
        file_suffix = drawing_styles[draw_style].name
        working_scene = get_working_scene().scene
        lineart_gp = create_lineart(source=subject, style=draw_style,
                scene=working_scene, cutter=cutter)
        ## In order to update lineart visibility set a frame (twice)
        bpy.context.scene.frame_set(1)
        bpy.context.scene.frame_set(1)
        svg_path = export_grease_pencil(subject, lineart_gp, remove, file_suffix)
        drawing_camera.restore_cam()
        subject.obj.hide_viewport = False 

    cutter.reset_solver()
        
