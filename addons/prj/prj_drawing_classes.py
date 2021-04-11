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
import mathutils
from mathutils import Vector
import prj
from prj import prj_utils


class Drawing_context:
    args: list[str]
    style: str
    subjects: list[bpy.types.Object]
    camera: bpy.types.Object ## bpy.types.Camera 
    frame_size: float ## tuple[float, float] ... try?
    camera_frame: dict[str,Vector]


    DEFAULT_STYLE: str = 'cp'
    RENDER_PATH: str = bpy.path.abspath(bpy.context.scene.render.filepath)
    RENDER_RESOLUTION_X: int = bpy.context.scene.render.resolution_x
    RENDER_RESOLUTION_Y: int = bpy.context.scene.render.resolution_y

    def __init__(self, args: list[str]):
        self.args = args
        self.style = self.__get_style()
        self.subjects, self.camera = self.__get_objects()

        self.frame_size = self.camera.data.ortho_scale

        cam_frame_local = [v * Vector((1,1,self.camera.data.clip_start)) 
                for v in self.camera.data.view_frame()]
        cam_frame = [self.camera.matrix_world @ v 
                for v in cam_frame_local]
        cam_frame_norm = mathutils.geometry.normal(cam_frame[:3])
        cam_frame_loc = (cam_frame[0] + cam_frame[2]) / 2
        self.camera_frame = {'location': cam_frame_loc, 
                'direction': cam_frame_norm}


    def __get_style(self) -> str:
        style = ''.join([a.replace('-', '') for a in self.args 
            if a.startswith('-')])
        if len(style) == 0:
            return self.DEFAULT_STYLE
        return style

    def __get_objects(self) -> tuple[list[bpy.types.Object], bpy.types.Object]:
        all_objs = ''.join([a.strip() for a in self.args 
            if not a.startswith('-')]).split(';')
        objs = []
        for ob in all_objs:
            if bpy.data.objects[ob].type == 'CAMERA':
                cam = bpy.data.objects[ob]
            elif prj.is_renderables(bpy.data.objects[ob]):
                objs.append(bpy.data.objects[ob])
        if not objs:
            objs = [ob for ob in bpy.context.selectable_objects 
                    if prj.is_renderables(ob)]
        return objs, cam
        
class Draw_maker:
    draw_context: Drawing_context

    def __init__(self, draw_context):
        self.drawing_context = draw_context

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context

    def draw(self, subject: 'Drawing_subject', draw_style: str, 
            remove: bool = True) -> str:

        cut_flag = 'c'
        la_gps = []
        ## Cut has to be the last style
        draw_style = prj_utils.move_to_last(cut_flag, list(draw_style))
        cuts_collection = bpy.data.collections.new(subject.name + '_cuts') \
                if cut_flag in draw_style else None
        for d_style in draw_style:
            draw_subject = subject

            if d_style == cut_flag and subject.cut_objects:

                for ob in subject.cut_objects:
                    prj_utils.apply_mod(ob)
                    cut = prj_utils.cut_object(obj = ob, 
                            cut_plane = self.drawing_context.camera_frame)
                    cut.location = cut.location + \
                            self.drawing_context.camera_frame['direction']
                    to_draw = cut
                    if subject.type == 'COLLECTION':
                        cuts_collection.objects.link(cut)
                        to_draw = cuts_collection

                scene = bpy.context.scene
                scene.collection.children.link(cuts_collection)
                draw_subject = Drawing_subject(to_draw, self.drawing_context)

            elif d_style == 'b':
                ## TODO
                pass
            
            la_gps.append(prj_utils.create_lineart(source=subject, style=d_style, 
                    la_source=draw_subject))
            ## Hide grease pencil line art to keep netxt calculations fast
            la_gps[-1].hide_viewport = True

        for la_gp in la_gps:
            la_gp.hide_viewport = False
        prj_utils.make_active(la_gp)
        bpy.ops.wm.gpencil_export_svg(filepath=subject.get_svg_path(), 
                selected_object_type='VISIBLE')
        if remove:
            bpy.data.objects.remove(la_gp, do_unlink=True)
        return subject.svg_path

class Drawing_subject:
    obj: bpy.types.Object
    drawing_context: Drawing_context
    visible: bool
    frontal: bool
    behind: bool
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: str
    visibility: dict[str, bool]
    objects_visibility: dict[str, list[bpy.types.Object]]
    cut_objects: list[bpy.types.Object]

    def __init__(self, obj, draw_context):
        self.obj = obj
        if (type(obj) == bpy.types.Object and obj.type == 'EMPTY'):
            self.obj = prj_utils.make_local_collection(self.obj)
        self.name = obj.name
        self.drawing_context = draw_context

        if type(self.obj) == bpy.types.Collection:
            self.type = 'COLLECTION'
            self.lineart_source_type = self.type
            self.objects = self.obj.all_objects
        else:
            self.type = obj.type
            self.lineart_source_type = 'OBJECT'
            self.objects = [obj]

        self.lineart_source = self.obj
        self.cut_objects = []
            
        self.visibility, self.objects_visibility = self.__get_visibility(
                linked = self.type == 'COLLECTION')
        self.visible = self.visibility['framed']
        self.grease_pencil = None
        for ob in self.objects:
            if ob in self.objects_visibility['frontal'] \
                    and ob in self.objects_visibility['behind']:
                self.cut_objects.append(ob) 

    #def set_draw_maker(self, draw_maker: Draw_maker) -> None:
    #    self.draw_maker = draw_maker

    #def get_draw_maker(self) -> Draw_maker:
    #    return self.draw_maker

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context

    def get_svg_path(self, prefix = None, suffix = None) -> str:
        path = self.drawing_context.RENDER_PATH
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        self.svg_path = f"{path}{sep}{pfx}{self.obj.name}{sfx}.svg"
        return self.svg_path

    def __get_visibility(self, linked: bool = True) -> dict[str, bool]:
        """ Get self.obj visibility (framed, frontal, behind camera) 
        and store individual visibilities in self.objects_visibility """
        visibility = {}
        objects_visibility = {}
        for obj in self.objects:
            framed = prj_utils.in_frame(self.drawing_context.camera, obj)
            for k in framed:
                if k not in objects_visibility:
                    objects_visibility[k] = []
                if framed[k]:
                    objects_visibility[k].append(obj)
                if len(visibility) == 3 and False not in visibility.values():
                    continue
                if k not in visibility:
                    visibility[k] = framed[k]
                    continue
                if not visibility[k] and framed[k]:
                    visibility[k] = framed[k]
        return visibility, objects_visibility
