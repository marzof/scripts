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
from prj.utils import make_active, create_lineart
from prj.drawing_style import drawing_styles
from prj.drawing_camera import get_drawing_camera
from prj.working_scene import get_working_scene

def export_grease_pencil(subject: 'Drawing_subject', 
        grease_pencil: bpy.types.Object, 
        remove: bool, svg_suffix: str = '') -> str:
    """ Export grease_pencil to svg and return its path """
    make_active(grease_pencil)

    svg_path = subject.get_svg_path(suffix=svg_suffix)
    
    svg_main_path = subject.svg_path
    svg_main_path.add_object_path(subject, svg_path, svg_suffix)

    bpy.ops.wm.gpencil_export_svg(filepath=svg_path, 
            selected_object_type='VISIBLE')
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
        
