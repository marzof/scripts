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
from prj import svg_lib
from prj import prj_utils
#import svgutils

print('\n\n\n###################################\n\n\n')

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
RENDER_PATH = bpy.path.abspath(bpy.context.scene.render.filepath)
#SVG_GROUP_PREFIX = 'blender_object_' + GREASE_PENCIL_PREFIX

class Drawing_context:
    args: list[str]
    style: str
    subjects: list[bpy.types.Object]
    camera: bpy.types.Object ## bpy.types.Camera 
    frame: bpy.types.Object ## bpy.types.GreasePencil (lineart)
    frame_size: float ## tuple[float, float] ... try?
    render_path: str
    viewed_objects: dict[str, bpy.types.Object]

    RENDERABLES: list[str] = ['MESH', 'CURVE', 'EMPTY']
    FRAME_NAME: str = 'frame'
    DEFAULT_STYLE: str = 'cp'
    OCCLUSION_LEVELS = { 'cp': (0,0), 'h': (1,128), 'b': (0,128), }

    def __init__(self, args: list[str], render_path: str):
        self.args = args
        self.style = self.get_style()
        self.subjects, self.camera = self.get_objects()
        self.frame_size = self.camera.data.ortho_scale
        self.frame = self.create_frame()
        self.render_path = render_path
        self.viewed_objects = prj_utils.viewed_objects(
                self.camera, self.subjects, self.RENDERABLES)
        self.subjects, self.camera = self.get_objects()
        if not self.subjects:
            self.subjects = self.viewed_objects['frontal']

    def get_style(self) -> str:
        style = ''.join([a.replace('-', '') for a in self.args 
            if a.startswith('-')])
        if not style == 0:
            return self.DEFAULT_STYLE
        return style

    def get_objects(self) -> tuple[list[bpy.types.Object], bpy.types.Object]:
        all_objs = ''.join([a.strip() for a in self.args 
            if not a.startswith('-')]).split(';')
        objs = []
        for o in all_objs:
            if bpy.data.objects[o].type == 'CAMERA':
                cam = bpy.data.objects[o]
            if bpy.data.objects[o].type in self.RENDERABLES:
                objs.append(bpy.data.objects[o])
        return objs, cam
        
    def create_frame(self) -> bpy.types.Object: ## GreasePencil (lineart)
        """ Create a plane at the clip end of cam with same size of cam frame """

        ## Get frame verts by camera dimension and put it at the camera clip end
        z = -(self.camera.data.clip_end - .01)
        print('z',z)
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
        prj_utils.make_active(subject.create_lineart('OBJECT', style))
        bpy.ops.wm.gpencil_export_svg(filepath=subject.get_svg_path(), 
                selected_object_type='VISIBLE')
        subject.unpose()
        subject.remove_lineart()
        return subject.svg_path

    def export(self):
        prj_utils.make_active(bpy.data.objects["Line Art"])
        bpy.ops.object.gpencil_modifier_apply(modifier="Line Art")
        print(bpy.context.active_object)
        bpy.ops.wm.gpencil_export_svg(filepath='/home/mf/Documents/test.svg', 
                selected_object_type='VISIBLE')

class Drawing_subject:
    obj: bpy.types.Object
    initial_rotation: mathutils.Euler
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: str
    draw_maker: Draw_maker
    draw_context: Drawing_context

    POSE_ROTATION: float = .000001

    def __init__(self, obj, draw_maker):
        self.obj = obj
        self.initial_rotation = obj.rotation_euler.copy()
        self.pose_rotation = self.POSE_ROTATION
        self.draw_maker = draw_maker
        self.drawing_context = draw_maker.drawing_context

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
        path = self.drawing_context.render_path
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        self.svg_path = f"{path}{sep}{pfx}{self.obj.name}{sfx}.svg"
        return self.svg_path

    def pose(self, rotation: float = POSE_ROTATION) -> None:
        """ Apply a small amount rotation to avoid lineart bugs """
        self.pose_rotation = rotation
        for i, angle in enumerate(self.obj.rotation_euler):
            self.obj.rotation_euler[i] = angle + self.pose_rotation

    def unpose(self) -> None:
        """ Reset obj to previous position """
        self.obj.rotation_euler = self.initial_rotation

    def create_lineart(self, source_type: str = 'OBJECT', style: str = 'cp') -> bpy.types.Object:
        if self.obj.type == 'EMPTY':
            source = self.obj.instance_collection
            source_type = 'COLLECTION'
            print('source', source)
            print('source_type', source_type)
        else:
            source = self.obj
        self.lineart = prj_utils.create_line_art_onto(source, source_type, 
                self.drawing_context.OCCLUSION_LEVELS[style][0], 
                self.drawing_context.OCCLUSION_LEVELS[style][1])
        return self.lineart

    def remove_lineart(self) -> None:
        print('remove', self.lineart)
        print(self.lineart.type)
        print(list(self.lineart.grease_pencil_modifiers))
        bpy.data.objects.remove(self.lineart, do_unlink=True)


svgs: list[str] = []

draw_context = Drawing_context(args = ARGS, render_path = RENDER_PATH)
draw_maker = Draw_maker(draw_context)
print(draw_context.viewed_objects)
draw_maker.export()
#for subj in draw_context.subjects:
#    print(subj.name)
#    svgs.append(draw_maker.draw(Drawing_subject(subj, draw_maker), 
#        draw_context.style))

#        for svg_f in svg_files:
#            svg, drawing_g, frame_g = svg_lib.read_svg(svg_f['path'],
#                    SVG_GROUP_PREFIX + svg_f['obj'],
#                    SVG_GROUP_PREFIX + CAM_SIZE_PLANE) 
#            svg_lib.write_svg(svg, drawing_g, frame_g, cam.data.ortho_scale, 
#                    svg_f['path'])
