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
from prj.utils import make_active, create_lineart
from prj.drawing_subject import Drawing_subject
from prj.drawing_context import STYLES


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
        
        svg_main_path = self.subject.svg_path
        svg_main_path.add_object_path(self.subject, svg_path, svg_suffix)

        bpy.ops.wm.gpencil_export_svg(filepath=svg_path, 
                selected_object_type='VISIBLE')
        if remove:
            bpy.data.objects.remove(grease_pencil, do_unlink=True)
            self.subject.set_grease_pencil(None)
        return svg_path

    def draw(self, subject: Drawing_subject, styles: str, cutter: 'Cutter',
            remove: bool = True) -> list[str]:
        """ Create a grease pencil for subject (and add a lineart modifier) for
            every draw_style. Then export the grease pencil """
        self.subject = subject
        cutter.set_source(self.subject)

        ## If cutter doesn't work switch boolean modifier to FAST solver
        if self.subject.is_cut:
            depsgraph = bpy.context.evaluated_depsgraph_get()
            depsgraph.update()
            evaluated_cutter = cutter.obj.evaluated_get(depsgraph)
            if not list(evaluated_cutter.data.vertices):
                cutter.change_solver('FAST')

        styles_to_process = [s for s in styles if 
                    getattr(subject, STYLES[s]['condition'])]
        for draw_style in styles_to_process:
            print('draw', subject.name, 'in style', draw_style)
            remove = draw_style != 'c'
            file_suffix = STYLES[draw_style]['name']
            lineart_gp = create_lineart(source=self.subject, style=draw_style,
                    scene=self.drawing_context.working_scene)
            ## In order to update lineart visibility set a frame (twice)
            bpy.context.scene.frame_set(1)
            bpy.context.scene.frame_set(1)
            svg_path = self.export_grease_pencil(lineart_gp, remove, file_suffix)
            self.drawing_camera.restore_cam()
            self.subject.obj.hide_viewport = False 

        cutter.reset_solver()
            
