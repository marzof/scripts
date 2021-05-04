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
from mathutils import Vector, geometry
import prj
from prj import prj_utils

import numpy as np
import math
from bpy_extras.object_utils import world_to_camera_view

import time
start_time = time.time()

format_svg_size = lambda x, y: (str(x) + 'mm', str(x) + 'mm')
RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch
SCANNING_STEP: float = .1

class Scanner:
    depsgraph: bpy.types.Depsgraph
    cam_z: float
    cam_up: Vector
    cam_direction: Vector
    frame: list[Vector]
    frame_origin: Vector
    frame_x_vector: Vector
    frame_y_vector: Vector
    frame_z_start: float
    scanning_area: dict[str,list[tuple[float]]]
    visible_objects: list[bpy.types.Object]
    checked_samples: list[tuple[float]]

    def __init__(self, depsgraph: bpy.types.Depsgraph, camera: bpy.types.Object,
            step: float = 1.0):
        self.depsgraph = depsgraph
        self.camera = camera
        self.step = step
        self.cam_z = camera.data.view_frame()[0].z
        self.cam_up = camera.matrix_world.to_quaternion() @ \
                Vector((0.0, 1.0, 0.0))
        self.cam_direction = camera.matrix_world.to_quaternion() @ \
                Vector((0.0, 0.0, -1.0))
        self.frame = [camera.matrix_world @ v for v in camera.data.view_frame()]
        self.frame_origin = self.frame[2]
        self.frame_x_vector = self.frame[1] - self.frame[2]
        self.frame_y_vector = self.frame[0] - self.frame[1]
        self.frame_z_start = -self.camera.data.clip_start
        self.scanning_area = {}
        self.visible_objects = []
        self.checked_samples = []

    def get_step(self) -> float:
        return self.step

    def set_step(self, step:float) -> None:
        self.step = step

    def __round_to_base(self, x: float, base: float, round_func):
        return base * round_func(x / base)

    def __2d_range(self, area: tuple[tuple[float]], step: float) \
            -> list[tuple[float]]:
        """ Get a list representing a 2-dimensional array covering the area 
            by step interval """
        y_min, y_max = area[0][1], area[1][1] + step
        x_min, x_max = area[0][0], area[1][0] + step
        samples = [(x, y) for y in np.arange(y_min, y_max, step) 
                for x in np.arange(x_min, x_max, step)]
        return samples

    def get_visible_objects(self) -> list[bpy.types.Object]:
        """ Populate self.visible_objetcs and return it """
        z = self.frame_z_start
        area_to_scan = ((0.0, 0.0, z), (1.0, 1.0, z))
        area_samples = self.__2d_range(area_to_scan, self.step)
        self.scanning_area[None] = area_samples
        self.scan_area(area_samples)
        return self.visible_objects

    def check_object_visibility(self, obj: bpy.types.Object) -> bool:
        """ Get true if obj is visible """
        area_to_scan = self.frame_obj_bound_rect(obj)
        if area_to_scan:
            z = self.frame_z_start
            area_to_scan = (area_to_scan[0] + (z,)), (area_to_scan[1] + (z,))
            area_samples = self.__2d_range(area_to_scan, self.step)
            self.scanning_area[obj.name] = area_samples
            return self.scan_area(area_samples, obj)

    def __get_ray_origin(self, v: tuple[float]) -> Vector:
        """ Get frame point moving origin in x and y direction by v factors"""
        x_coord = self.frame_origin + (self.frame_x_vector * v[0])
        coord = x_coord + (self.frame_y_vector * v[1])
        return Vector(coord)

    def scan_area(self, area: list[tuple[float]], 
            target: bpy.types.Object = None) -> bool:
        """ Scan area by its samples and populate self.visible_objects.
            Return True if get target """
        for sample in area:
            if sample not in self.checked_samples:
                self.checked_samples.append(sample)
                ray_origin = self.__get_ray_origin(sample)
                res, loc, nor, ind, obj, mat = bpy.context.scene.ray_cast(
                    self.depsgraph, ray_origin, self.cam_direction)
                if obj and obj not in self.visible_objects:
                    self.visible_objects.append(obj)
                    if obj == target:
                        return True
        return False

    def frame_obj_bound_rect(self, obj: bpy.types.Object) -> tuple[tuple[float]]:
        """ Get the bounding rect of obj in cam view coords """
        world_obj_bbox = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
        bbox_from_cam_view = [world_to_camera_view(bpy.context.scene, 
            self.camera, v) for v in world_obj_bbox]
        bbox_xs = [v.x for v in bbox_from_cam_view]
        bbox_ys = [v.y for v in bbox_from_cam_view]
        x_min, x_max = max(0.0, min(bbox_xs)), min(1.0, max(bbox_xs))
        y_min, y_max = max(0.0, min(bbox_ys)), min(1.0, max(bbox_ys))
        if x_min > 1 or x_max < 0 or y_min > 1 or y_max < 0:
            ## obj is out of frame
            return None
        x_min_round = self.__round_to_base(x_min, self.step, math.floor)
        x_max_round = self.__round_to_base(x_max, self.step, math.ceil)
        y_min_round = self.__round_to_base(y_min, self.step, math.floor)
        y_max_round = self.__round_to_base(y_max, self.step, math.ceil)
        return (x_min_round, y_min_round), (x_max_round, y_max_round)

class Drawing_context:
    args: list[str]
    style: str
    selected_subjects: list[bpy.types.Object]
    subjects: list[bpy.types.Object]
    camera: bpy.types.Object ## bpy.types.Camera 
    depsgraph: bpy.types.Depsgraph
    frame_size: float ## tuple[float, float] ... try?
    camera_frame: dict[str,Vector]


    DEFAULT_STYLE: str = 'pc'
    RENDER_PATH: str = bpy.path.abspath(bpy.context.scene.render.filepath)
    RENDER_RESOLUTION_X: int = bpy.context.scene.render.resolution_x
    RENDER_RESOLUTION_Y: int = bpy.context.scene.render.resolution_y

    def __init__(self, args: list[str]):
        self.args = args
        self.style = self.__get_style()
        self.selected_subjects, self.camera = self.__get_objects()
        self.depsgraph = bpy.context.evaluated_depsgraph_get()
        self.depsgraph.update()

        self.frame_size = self.camera.data.ortho_scale
        self.camera_frame = self.__get_camera_frame()
        self.scanner = Scanner(self.depsgraph, self.camera, SCANNING_STEP)
        if not self.selected_subjects:
            self.subjects = self.scanner.get_visible_objects()
        else:
            self.subjects = [obj for obj in self.selected_subjects if \
                    obj not in self.scanner.visible_objects and
                    self.scanner.check_object_visibility(obj)]

        self.svg_size = format_svg_size(self.frame_size * 10, 
                self.frame_size * 10)
        self.svg_factor = self.frame_size/self.RENDER_RESOLUTION_X * \
                RESOLUTION_FACTOR
        self.svg_styles = [prj.STYLES[d_style]['name'] for d_style in 
                self.style]

    def __get_camera_frame(self) -> dict[str, Vector]:
        cam_frame_local = [v * Vector((1,1,self.camera.data.clip_start)) 
                for v in self.camera.data.view_frame()]
        cam_frame = [self.camera.matrix_world @ v for v in cam_frame_local]
        cam_frame_origin = cam_frame[2]
        cam_frame_x_vector = cam_frame[1] - cam_frame[2]
        cam_frame_y_vector = cam_frame[0] - cam_frame[1]
        cam_frame_loc = (cam_frame[0] + cam_frame[2]) / 2
        cam_frame_norm = geometry.normal(cam_frame[:3])
        return {'location': cam_frame_loc, 
                'origin': cam_frame_origin,
                'x_vector': cam_frame_x_vector,
                'y_vector': cam_frame_y_vector,
                'direction': cam_frame_norm}

    def __get_style(self) -> str:
        style = ''.join([a.replace('-', '') for a in self.args 
            if a.startswith('-')])
        if len(style) == 0:
            return self.DEFAULT_STYLE
        ## Cut has to be the last style
        if 'c' in style:
            style = [l for l in style if l != 'c'] + ['c']
        return style

    def __get_objects(self) -> tuple[list[bpy.types.Object], bpy.types.Object]:
        arg_objs = [a.strip() for a in self.args if not a.startswith('-')]
        all_objs = ''.join(arg_objs).split(';') if arg_objs \
                else [obj.name for obj in bpy.context.selected_objects]
        objs = []
        for ob in all_objs:
            if bpy.data.objects[ob].type == 'CAMERA':
                cam = bpy.data.objects[ob]
            elif prj.is_renderables(bpy.data.objects[ob]):
                objs.append(bpy.data.objects[ob])
        return objs, cam
        
class Draw_maker:
    draw_context: Drawing_context

    def __init__(self, draw_context):
        self.drawing_context = draw_context

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context
    
    def export_grease_pencil(self, grease_pencil: bpy.types.Object, 
            remove: bool) -> str:
        """ Export grease_pencil to svg and return its path """
        prj_utils.make_active(grease_pencil)

        svg_path = self.subject.get_svg_path()
        bpy.ops.wm.gpencil_export_svg(filepath=svg_path, 
                selected_object_type='VISIBLE')
        if remove:
            bpy.data.objects.remove(grease_pencil, do_unlink=True)
        return self.subject.svg_path

    def __create_lineart_grease_pencil(self, drawing_style: str) \
            -> bpy.types.Object:
        """ Create a grease pencil with lineart modifier according to 
            drawing_style """
        get_subject = getattr(globals()['Drawing_subject'], 
                prj.STYLES[drawing_style]['subject'])
        draw_subject = get_subject(self.subject)
        if not draw_subject:
            return None
        lineart_gp = prj_utils.create_lineart(source=self.subject, 
            style=drawing_style, la_source=draw_subject)
        ## Hide grease pencil line art to keep next calculations fast
        lineart_gp.hide_viewport = True
        return lineart_gp

    def draw(self, subject: 'Drawing_subject', draw_style: str, 
            remove: bool = True) -> str:
        """ Create a grease pencil for subject and add a lineart modifier for
            every draw_style. 
            Then export the grease pencil and return its filepath """
        self.subject = subject
        for drawing_style in draw_style:
            la_gp = self.__create_lineart_grease_pencil(drawing_style)
            if la_gp: lineart_gp = la_gp

        lineart_gp.hide_viewport = False
        svg_path = self.export_grease_pencil(lineart_gp, remove)
        return svg_path


class Drawing_subject:
    obj: bpy.types.Object
    drawing_context: Drawing_context
    #visible: bool
    #frontal: bool
    #behind: bool
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: str
    #visibility: dict[str, bool]
    #objects_visibility: dict[str, list[bpy.types.Object]]
    #cut_objects: list[bpy.types.Object]

    def __init__(self, obj, draw_context):
        self.obj = obj
        if (type(obj) == bpy.types.Object and obj.type == 'EMPTY'):
            self.obj = prj_utils.make_local_collection(self.obj)
        self.name = obj.name
        self.drawing_context = draw_context
        self.collections = [coll.name for coll in obj.users_collection]

        if type(self.obj) == bpy.types.Collection:
            self.type = 'COLLECTION'
            self.lineart_source_type = self.type
            self.objects = self.obj.all_objects
        else:
            self.type = obj.type
            self.lineart_source_type = 'OBJECT'
            self.objects = [obj]

        self.lineart_source = self.obj
        #self.cut_objects = []
            
        #self.visibility, self.objects_visibility = self.__get_visibility(
        #        linked = self.type == 'COLLECTION')
        #self.visible = self.visibility['framed']
        self.grease_pencil = None
        #self.cut_objects = [ob for ob in self.objects 
        #        if ob in self.objects_visibility['frontal'] 
        #        and ob in self.objects_visibility['behind']]

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context

    def get_svg_path(self, prefix = None, suffix = None) -> str:
        """ Return the svg filepath with prefix or suffix """
        path = self.drawing_context.RENDER_PATH
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        self.svg_path = f"{path}{sep}{pfx}{self.obj.name}{sfx}.svg"
        return self.svg_path

    #def __get_visibility(self, linked: bool = True) -> dict[str, bool]:
    #    """ Get self.obj visibility (framed, frontal, behind camera) 
    #    and store individual visibilities in self.objects_visibility """
    #    visibility = {}
    #    objects_visibility = {}
    #    for obj in self.objects:
    #        framed = prj_utils.in_frame(self.drawing_context.camera, obj)
    #        for k in framed:
    #            if k not in objects_visibility:
    #                objects_visibility[k] = []
    #            if framed[k]:
    #                objects_visibility[k].append(obj)
    #            if len(visibility) == 3 and False not in visibility.values():
    #                continue
    #            if k not in visibility:
    #                visibility[k] = framed[k]
    #                continue
    #            if not visibility[k] and framed[k]:
    #                visibility[k] = framed[k]
    #    return visibility, objects_visibility

    def get_cut_subject(self) -> 'Drawing_subject':
        if not self.cut_objects:
            return None
        cuts_collection = bpy.data.collections.new(self.name + '_cuts')
        for ob in self.cut_objects:
            prj_utils.apply_mod(ob)
            cut = prj_utils.cut_object(obj = ob, 
                    cut_plane = self.drawing_context.camera_frame)
            cut.location = cut.location + \
                    self.drawing_context.camera_frame['direction']
            to_draw = cut
            if self.type == 'COLLECTION':
                cuts_collection.objects.link(cut)
                to_draw = cuts_collection

    #    bpy.context.scene.collection.children.link(cuts_collection)
    #    return Drawing_subject(to_draw, self.drawing_context)

    def get_projected_subject(self) -> 'Drawing_subject':
            return self

    def get_back_subject(self) -> 'Drawing_subject':
        ## TODO
        pass
