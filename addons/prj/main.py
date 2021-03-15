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

print('\n\n\n###################################\n\n\n')

import bpy, bmesh
import sys, os
import ast, random
from prj import blend2svg
from prj import svg_lib
from prj import prj_utils
import mathutils
from mathutils import Vector
from mathutils import geometry
from mathutils import Matrix
#import svgutils
from bpy_extras.object_utils import world_to_camera_view

undotted = lambda x: x.replace('.', '_')

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
RENDER_PATH = bpy.path.abspath(bpy.context.scene.render.filepath)
RENDERABLES = ['MESH', 'CURVE', 'EMPTY']
OCCLUSION_LEVELS = { 'cp': (0,0), 'h': (1,128), 'b': (0,128), }

CAM_SIZE_PLANE = 'size_frame'
#SVG_GROUP_PREFIX = 'blender_object_' + GREASE_PENCIL_PREFIX

## FLAGS = ARGS[0].replace('-', '') if ARGS else 'cp'
## ASSETS = ARGS[1] if ARGS else str(get_render_assets_cl())

class Drawing_subject:

    obj: bpy.types.Object
    initial_rotation: mathutils.Euler
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: str

    def __init__(self, obj):
        self.obj = obj
        self.initial_rotation = obj.rotation_euler.copy()

    def get_svg_path(self, path, prefix = None, suffix = None) -> str:
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        self.svg_path = f"{path}{sep}{pfx}{self.obj.name}{sfx}.svg"
        return self.svg_path

    def pose(self, amount) -> None:
        """ Apply a small amount rotation to avoid lineart bugs """
        for i, angle in enumerate(self.obj.rotation_euler):
            self.obj.rotation_euler[i] = angle + amount

    def unpose(self) -> None:
        """ Reset obj to previous position """
        self.obj.rotation_euler = self.initial_rotation

    def get_lineart(self, style) -> bpy.types.Object:
        self.lineart = prj_utils.create_line_art_onto(self.obj, 'OBJECT', 
                OCCLUSION_LEVELS[style][0], OCCLUSION_LEVELS[style][1])
        return self.lineart

    def remove_lineart(self) -> None:
        bpy.data.objects.remove(self.lineart, do_unlink=True)


class Draw_maker:

    render_path: str
    rotation_fix: float

    def __init__(self, render_path, rotation_fix = .000001):
        self.render_path = render_path
        self.rotation_fix = rotation_fix

    def draw(self, subject: Drawing_subject, style: str) -> str:
        subject.pose(self.rotation_fix)
        prj_utils.make_active(subject.get_lineart(style))
        bpy.ops.wm.gpencil_export_svg(
           filepath=subject.get_svg_path(self.render_path), 
           selected_object_type='VISIBLE')
        subject.unpose()
        subject.remove_lineart()
        return subject.svg_path

class Drawing_context:

    style: str
    frame_size: float ## tuple[float, float] ... try?
    subjects: list[bpy.types.Object]
    camera: bpy.types.Object ## bpy.types.Camera 

    def __init__(self, args):
        self.args = args
        self.style = self.get_style()
        self.subjects, self.camera = self.get_objects()
        self.frame_size = self.camera.data.ortho_scale
        self.frame = self.create_frame()

    def get_style(self) -> str:
        style = ''.join([a.replace('-', '') for a in self.args 
            if a.startswith('-')])
        return style

    def get_objects(self) -> tuple[list[bpy.types.Object], bpy.types.Object]:
        all_objs = ''.join([a.strip() for a in self.args 
            if not a.startswith('-')]).split(';')
        objs = []
        for o in all_objs:
            if bpy.data.objects[o].type in RENDERABLES:
                objs.append(bpy.data.objects[o])
            if bpy.data.objects[o].type == 'CAMERA':
                cam = bpy.data.objects[o]
        return objs, cam
        
    def create_frame(self) -> bpy.types.Object: ## GreasePencil (lineart)
        """ Create a plane at the clip end of cam with same size of cam frame """
        frame_mesh = bpy.data.meshes.new(CAM_SIZE_PLANE)
        frame_obj = bpy.data.objects.new(CAM_SIZE_PLANE, frame_mesh)

        bpy.context.collection.objects.link(frame_obj)

        bm = bmesh.new()
        bm.from_object(frame_obj, bpy.context.view_layer.depsgraph)

        for v in self.camera.data.view_frame():
            bm.verts.new(v[:2] + (-(self.camera.data.clip_end - .01),))

        bmesh.ops.contextual_create(bm, geom=bm.verts)

        bm.to_mesh(frame_mesh)
        bm.free()
        frame_obj.matrix_world = self.camera.matrix_world
        frame_la_gp = prj_utils.create_line_art_onto(frame_obj, 'OBJECT', 
                OCCLUSION_LEVELS['b'][0], OCCLUSION_LEVELS['b'][1])
        return frame_la_gp


svgs: list[str] = []

draw_context = Drawing_context(ARGS)

draw_maker = Draw_maker(RENDER_PATH)
for subj in draw_context.subjects:
    svgs.append(draw_maker.draw(Drawing_subject(subj), draw_context.style))

#        for svg_f in svg_files:
#            svg, drawing_g, frame_g = svg_lib.read_svg(svg_f['path'],
#                    SVG_GROUP_PREFIX + svg_f['obj'],
#                    SVG_GROUP_PREFIX + CAM_SIZE_PLANE) 
#            svg_lib.write_svg(svg, drawing_g, frame_g, cam.data.ortho_scale, 
#                    svg_f['path'])
