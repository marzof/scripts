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
from prj.utils import create_lineart, make_active
from prj.drawing_subject import Drawing_subject

class Draw_maker:
    draw_context: 'Drawing_context'

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
        draw_subject = self.subject
        if not draw_subject:
            return None
        lineart_gp = create_lineart(source=self.subject, 
            style=drawing_style, la_source=draw_subject)
        ## Hide grease pencil line art to keep next calculations fast
        #lineart_gp.hide_viewport = True
        return lineart_gp

    def draw(self, subject: Drawing_subject, styles: str, 
            remove: bool = True) -> list[str]:
        """ Create a grease pencil for subject and add a lineart modifier for
            every draw_style. 
            Then export the grease pencil and return its filepath """
        self.subject = subject
        svg_paths = []
        styles_to_process = [s for s in styles if 
                    getattr(subject, prj.STYLES[s]['condition'])]
        for draw_style in styles_to_process:
            print('draw', subject.name, 'in style', draw_style)
            file_suffix = prj.STYLES[draw_style]['name']
            self.drawing_camera.set_cam_for_style(draw_style)
            lineart_gp = self.__create_lineart_grease_pencil(draw_style)
            if not lineart_gp: 
                continue
            #lineart_gp.hide_viewport = False
            svg_paths.append(self.export_grease_pencil(
                lineart_gp, remove, file_suffix))
            self.drawing_camera.restore_cam()
        return svg_paths

