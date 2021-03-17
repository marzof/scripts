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
import sys, os
import mathutils
from prj import prj_utils
from prj import prj_svglib
from prj.prj_svglib import Svg_drawing

print('\n\n\n###################################\n\n\n')

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]

class Drawing_context:
    args: list[str]
    style: str
    subjects: list[bpy.types.Object]
    camera: bpy.types.Object ## bpy.types.Camera 
    frame: bpy.types.Object ## bpy.types.GreasePencil (lineart)
    frame_size: float ## tuple[float, float] ... try?

    __renderables = lambda self, obj: (obj.type, bool(obj.instance_collection)) \
            in [('MESH', False), ('CURVE', False), ('EMPTY', True)]

    FRAME_NAME: str = 'frame'
    DEFAULT_STYLE: str = 'cp'
    OCCLUSION_LEVELS = { 'cp': (0,0), 'h': (1,128), 'b': (0,128), }
    RENDER_PATH: str = bpy.path.abspath(bpy.context.scene.render.filepath)
    GREASE_PENCIL_PREFIX = 'prj_'
    SVG_GROUP_PREFIX = 'blender_object_' + GREASE_PENCIL_PREFIX

    def __init__(self, args: list[str]):
        self.args = args
        self.style = self.__get_style()
        self.subjects, self.camera = self.__get_objects()
        self.frame_size = self.camera.data.ortho_scale
        self.frame = self.__create_frame()

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
            if self.__renderables(bpy.data.objects[ob]):
                objs.append(bpy.data.objects[ob])
        if not objs:
            objs = [ob for ob in bpy.context.selectable_objects 
                    if self.__renderables(ob)]
        return objs, cam
        
    def __create_frame(self) -> bpy.types.Object: ## GreasePencil (lineart)
        """ Create a plane at the clip end of cam with same size of cam frame """

        ## Get frame verts by camera dimension and put it at the camera clip end
        z = -(self.camera.data.clip_end - .01)
        verts = [v[:2] + (z,) for v in self.camera.data.view_frame()]
        frame_obj = prj_utils.mesh_by_verts(self.FRAME_NAME, verts)

        ## Align frame to camera orientation and position
        frame_obj.matrix_world = self.camera.matrix_world
        
        ## Create the grease pencil with lineart modifier
        frame_la_gp = prj_utils.create_line_art_onto(frame_obj, 'OBJECT', 
                self.OCCLUSION_LEVELS['b'][0], self.OCCLUSION_LEVELS['b'][1])

        return frame_la_gp

class Draw_maker:
    draw_context: Drawing_context

    def __init__(self, draw_context):
        self.drawing_context = draw_context

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context

    def draw(self, subject: 'Drawing_subject', style: str) -> str:
        subject.pose()
        prj_utils.make_active(subject.create_lineart())
        bpy.ops.wm.gpencil_export_svg(filepath=subject.get_svg_path(), 
                selected_object_type='VISIBLE')
        subject.unpose()
        subject.remove_lineart()
        return subject.svg_path

class Drawing_subject:
    obj: bpy.types.Object
    initial_rotation: mathutils.Euler
    draw_maker: Draw_maker
    drawing_context: Drawing_context
    visibility: dict[str, bool]
    framed: bool
    frontal: bool
    behind: bool
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: str

    POSE_ROTATION: float = .00001

    def __init__(self, obj, draw_maker):
        self.obj = obj
        self.pose_rotation = self.POSE_ROTATION
        self.draw_maker = draw_maker
        self.drawing_context = draw_maker.drawing_context
        self.type = obj.type

        self.lineart_source = obj
        self.lineart_source_type = 'OBJECT'
        self.objects = [obj]
        if self.type == 'EMPTY':
            self.lineart_source = self.__make_local_collection()
            self.lineart_source_type = 'COLLECTION'
            self.objects = self.lineart_source.objects
            
        self.visibility = self.__get_visibility(linked = self.type == 'EMPTY')
        self.initial_rotation = [o.rotation_euler.copy() for o in self.objects]
        self.framed = self.visibility['framed']
        self.frontal = self.visibility['frontal']
        self.behind = self.visibility['behind']

    def set_draw_maker(self, draw_maker: Draw_maker) -> None:
        self.draw_maker = draw_maker

    def get_draw_maker(self) -> Draw_maker:
        return self.draw_maker

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context

    def set_pose_rotation(self, value: float) -> None:
        self.pose_rotation = value

    def get_pose_rotation(self) -> float:
        return self.pose_rotation

    def get_svg_path(self, prefix = None, suffix = None) -> str:
        path = self.drawing_context.RENDER_PATH
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        self.svg_path = f"{path}{sep}{pfx}{self.obj.name}{sfx}.svg"
        return self.svg_path

    def pose(self, rotation: float = POSE_ROTATION) -> None:
        """ Apply a small amount rotation to avoid lineart bugs """
        self.pose_rotation = rotation
        for obj in self.objects:
            for i, angle in enumerate(obj.rotation_euler):
                obj.rotation_euler[i] = angle + self.pose_rotation

    def unpose(self) -> None:
        """ Reset obj to previous position """
        for i, obj in enumerate(self.objects):
            obj.rotation_euler = self.initial_rotation[i]

    def create_lineart(self) -> bpy.types.Object:
        context = self.drawing_context
        self.lineart = prj_utils.create_line_art_onto(
                self.lineart_source, self.lineart_source_type, 
                context.OCCLUSION_LEVELS[context.style][0], 
                context.OCCLUSION_LEVELS[context.style][1])
        return self.lineart

    def remove_lineart(self) -> None:
        bpy.data.objects.remove(self.lineart, do_unlink=True)
    
    def __make_local_collection(self) -> bpy.types.Collection:
        ''' Convert linked object to local object '''
        f_path = self.obj.instance_collection.library.filepath
        with bpy.data.libraries.load(f_path, relative=False) as (data_from, data_to):
            data_to.collections.append(self.obj.instance_collection.name)
        self.collection = bpy.data.collections[-1]
        self.collection.name = self.obj.name
        scene = bpy.context.scene
        scene.collection.children.link(self.collection)
        return self.collection

    def __get_visibility(self, linked: bool = True) -> dict[str, bool]:
        """ Get self.obj visibility (framed, frontal, behind camera) 
        and store individual visibilities in self.objects_visibility """
        self.objects_visibility = []
        visibility = {}
        for obj in self.objects:
            relocated_obj = prj_utils.localize_obj(self.obj, obj) if linked \
                    else obj
            framed = prj_utils.in_frame(self.drawing_context.camera, 
                    relocated_obj)
            self.objects_visibility.append(framed)
            for k in framed:
                if len(visibility) == 3 and False not in visibility.values():
                    break
                if k not in visibility:
                    visibility[k] = framed[k]
                    continue
                if not visibility[k] and framed[k]:
                    visibility[k] = framed[k]
        return visibility


drawings: list[Svg_drawing] = []

draw_context = Drawing_context(args = ARGS)
draw_maker = Draw_maker(draw_context)
for subj in draw_context.subjects:
    print(subj.name)
    drawings.append(Svg_drawing(draw_maker.draw(Drawing_subject(subj, draw_maker),
        draw_context.style), draw_context))
    #d = drawings[-1]
    #frame_loc_size = prj_svglib.get_rect_loc_size(d.svg, 
    #        SVG_GROUP_PREFIX + draw_context.FRAME_NAME)
    #frame_size = frame_loc_size['dimensions'][0]
    #print(prj_svglib.pixel_to_mm(frame_size, frame_size, draw_context.frame_size))
#for svg_f in svgs:
    #svg, drawing_g, frame_g = svg_lib.read_svg(svgs[-1],
    #        SVG_GROUP_PREFIX + subj.name, 
    #        SVG_GROUP_PREFIX + draw_context.FRAME_NAME)
    #svg_lib.write_svg(svg, drawing_g, frame_g, draw_context.frame_size, svgs[-1])
