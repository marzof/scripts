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
from mathutils import Vector, geometry, Matrix
import prj
from prj import prj_utils
from pathlib import Path
import ast

import numpy as np
import math
from bpy_extras.object_utils import world_to_camera_view

import time
start_time = time.time()

format_svg_size = lambda x, y: (str(x) + 'mm', str(x) + 'mm')
RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch
SCANNING_STEP: float = .2
RAY_CAST_FILENAME: str = 'ray_cast'
ROUNDING: int = 6

def range_2d(area: tuple[tuple[float]], step: float) -> list[tuple[float]]:
    """ Get a list representing a 2-dimensional array covering the area 
        by step interval """
    x_min, x_max = area[0][0], area[1][0] + step
    y_min, y_max = area[0][1], area[1][1] + step
    samples = [(round(x, 6), round(y,  6)) \
            for y in np.arange(y_min, y_max, step) 
            for x in np.arange(x_min, x_max, step)]
    return samples

def round_to_base(x: float, base: float, round_func, 
        rounding: int = ROUNDING) -> float:
    """ Use rounding function to round x to base (for instance: 
        x = 4.77, base = 0.5, round_func = math.floor -> return 4.5 ) """
    return round(base * round_func(x / base), rounding)

def get_obj_bound_box(obj: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> \
        list[Vector]:
    """ Get the bounding box of obj in world coords. For collection instances 
        calculate the bounding box for all the objects """
    obj_bbox = []
    for obj_inst in depsgraph.object_instances:
        is_obj_instance = obj_inst.is_instance and \
                obj_inst.parent.name == obj.name
        is_obj = obj_inst.object.name == obj.name
        if is_obj_instance or is_obj:
            bbox = obj_inst.object.bound_box
            obj_bbox += [obj_inst.object.matrix_world @ Vector(v) \
                    for v in bbox]
    if is_obj:
        return obj_bbox
    ## It's a group of objects: get the overall bounding box
    bbox_xs, bbox_ys, bbox_zs = [], [], []
    for v in obj_bbox:
        bbox_xs.append(v.x)
        bbox_ys.append(v.y)
        bbox_zs.append(v.z)
    x_min, x_max = min(bbox_xs), max(bbox_xs)
    y_min, y_max = min(bbox_ys), max(bbox_ys)
    z_min, z_max = min(bbox_zs), max(bbox_zs)
    bound_box = [
            Vector((x_min, y_min, z_min)),
            Vector((x_min, y_min, z_max)),
            Vector((x_min, y_max, z_max)),
            Vector((x_min, y_max, z_min)),
            Vector((x_max, y_min, z_min)),
            Vector((x_max, y_min, z_max)),
            Vector((x_max, y_max, z_max)),
            Vector((x_max, y_max, z_min))]
    return bound_box

class Scanner:
    depsgraph: bpy.types.Depsgraph

    def __init__(self, depsgraph: bpy.types.Depsgraph, 
            draw_camera: 'Drawing_camera', step: float = 1.0):
        self.depsgraph = depsgraph
        self.draw_camera = draw_camera
        self.step = step

    def get_step(self) -> float:
        return self.step

    def set_step(self, step:float) -> None:
        self.step = step

    def __get_ray_origin(self, v: tuple[float], camera: 'Drawing_camera') -> \
            Vector:
        """ Get frame point moving origin in x and y direction by v factors"""
        x_coord = camera.frame_origin + (camera.frame_x_vector * v[0])
        coord = x_coord + (camera.frame_y_vector * v[1])
        return Vector(coord)

    def scan_area(self, area_samples: list[tuple[float]], 
            camera: 'Drawing_camera') -> dict[tuple[float],bpy.types.Object]:
        """ Scan area by its samples and return checked_samples maps """
        checked_samples = {}
        print('total area to scan', len(area_samples))
        for sample in area_samples:
            checked_samples[sample] = None
            ray_origin = self.__get_ray_origin(sample, self.draw_camera)
            res, loc, nor, ind, obj, mat = bpy.context.scene.ray_cast(
                self.depsgraph, ray_origin, camera.direction)
            if not obj:
                continue
            checked_samples[sample] = obj
        return checked_samples
    
class Drawing_camera:
    obj: bpy.types.Object
    name: str
    scanner: Scanner
    path: str
    direction: Vector
    frame: list[Vector]
    frame_origin: Vector
    frame_x_vector: Vector
    frame_y_vector: Vector
    frame_z_start: float
    ray_cast_filepath: str
    ray_cast: dict[tuple[float], str]
    checked_samples: dict[tuple[float], bpy.types.Object]
    objects_to_draw: list[bpy.types.Object]
    clip_start: float
    clip_end: float
    matrix: Matrix


    def __init__(self, camera: bpy.types.Object, draw_context: 'Drawing_context'):
        self.obj = camera
        self.name = camera.name
        self.draw_context = draw_context
        self.scanner = Scanner(draw_context.depsgraph, self, SCANNING_STEP)
        self.path = self.get_path()
        self.direction = camera.matrix_world.to_quaternion() @ \
                Vector((0.0, 0.0, -1.0))
        self.frame = [camera.matrix_world @ v for v in camera.data.view_frame()]
        self.frame_origin = self.frame[2]
        self.frame_x_vector = self.frame[1] - self.frame[2]
        self.frame_y_vector = self.frame[0] - self.frame[1]
        self.frame_z_start = -camera.data.clip_start

        self.ray_cast_filepath = os.path.join(self.path, RAY_CAST_FILENAME)
        self.ray_cast = self.get_ray_cast_data()
        self.checked_samples = {}
        self.objects_to_draw = self.draw_context.selected_subjects

        self.clip_start = camera.data.clip_start
        self.clip_end = camera.data.clip_end
        self.matrix = camera.matrix_world
    
    def __get_cam_data(self) -> None:
        """ Get data for back view """
        self.inverse_matrix = Matrix().Scale(-1, 4, (.0,.0,1.0))

        normal_vector = Vector((0.0, 0.0, -2 * self.clip_start))
        z_scale = round(self.matrix.to_scale().z, 4)
        opposite_matrix = Matrix().Scale(z_scale, 4, (.0,.0,1.0))
        base_matrix = self.matrix @ opposite_matrix
        translation = base_matrix.to_quaternion() @ (normal_vector * z_scale)

        self.translate_matrix = Matrix.Translation(translation)

    def get_path(self) -> str:
        """ Return folder path named after camera (create it if needed) """
        cam_path = os.path.join(self.draw_context.RENDER_BASEPATH, self.name)
        try:
            os.mkdir(cam_path)
        except OSError:
            print (f'{cam_path} already exists. Going on')
        return cam_path

    def frame_obj_bound_rect(self, obj: bpy.types.Object) -> tuple[tuple[float]]:
        """ Get the bounding rect of obj in cam view coords 
            (rect is just greater than object and accords with the step grid)"""
        world_obj_bbox = get_obj_bound_box(obj, self.draw_context.depsgraph)
        bbox_from_cam_view = [world_to_camera_view(bpy.context.scene, 
            self.obj, v) for v in world_obj_bbox]
        bbox_xs = [v.x for v in bbox_from_cam_view]
        bbox_ys = [v.y for v in bbox_from_cam_view]
        x_min, x_max = max(0.0, min(bbox_xs)), min(1.0, max(bbox_xs))
        y_min, y_max = max(0.0, min(bbox_ys)), min(1.0, max(bbox_ys))
        if x_min > 1 or x_max < 0 or y_min > 1 or y_max < 0:
            ## obj is out of frame
            return None
        x_min_round = round_to_base(x_min, self.scanner.step, math.floor)
        x_max_round = round_to_base(x_max, self.scanner.step, math.ceil)
        y_min_round = round_to_base(y_min, self.scanner.step, math.floor)
        y_max_round = round_to_base(y_max, self.scanner.step, math.ceil)
        return (x_min_round, y_min_round), (x_max_round, y_max_round) 
        
    def scan_all(self) -> None:
        """ Scan all the camera frame """
        area_to_scan = ((0.0, 0.0), (1.0, 1.0))
        area_samples = range_2d(area_to_scan, self.scanner.step)
        self.scan_area(area_samples)

    def scan_object_area(self, subj: 'Drawing_subject') -> None:
        """ Scan the area of subj """
        obj = subj.obj
        area_to_scan = self.frame_obj_bound_rect(obj)
        print('area to scan', area_to_scan)
        if area_to_scan:
            area_samples = range_2d(area_to_scan, self.scanner.step)
            print('area samples\n', area_samples)
            self.scan_area(area_samples)

    def scan_previous_obj_area(self, obj_name: str) -> None:
        """ Scan the area where obj was """
        samples = []
        for sample, obj in self.ray_cast.items():
            if obj == obj_name:
               samples.append(sample)
        self.scan_area(samples)

    def scan_area(self, area_samples: list[tuple[float]]) -> None:
        """ Scan area_samples and update ray_cast """
        new_samples = [sample for sample in area_samples \
                if sample not in self.checked_samples]
        checked_samples = self.scanner.scan_area(new_samples, self)
        ## Update checked_samples, ray_cast and objects_to_draw
        for sample in checked_samples:
            self.checked_samples[sample] = checked_samples[sample]
        changed_subjects = self.update_ray_cast(checked_samples)
        self.objects_to_draw = list(set(self.objects_to_draw + changed_subjects))

    def get_ray_cast_data(self) -> dict:
        """ Get data (in a dictionary) from ray_cast file if it exists 
            (or creates it if missing )"""
        data = {}
        try:
            with open(self.ray_cast_filepath) as f:
                for line in f:
                    sample = ast.literal_eval(line)
                    data[sample[0]] = sample[1]
            return data
        except OSError:
            print (f"{self.ray_cast_filepath} doesn't exists. Create it now")
            f = open(self.ray_cast_filepath, 'w')
            f.close()
            return data
    
    def write_ray_cast(self) -> None:
        """ Write ray_cast to file """
        with open(self.ray_cast_filepath, 'w') as f:
            for sample in self.ray_cast:
                value = self.ray_cast[sample] 
                ## Add quotes to actual object name for correct value passing
                string_value = f'"{value}"' if value else value
                f.write(f'{sample}, {string_value}\n')

    def update_ray_cast(self, 
            checked_samples: dict[tuple[float], bpy.types.Object]) -> None:
        """ Compare checked_samples (scan result) with ray_cast data, 
            update them and return changed_subjects"""
        changed_subjects = []
        for sample in checked_samples:
            obj = checked_samples[sample]
            prev_sample_value = self.ray_cast[sample] \
                    if sample in self.ray_cast else None
            prev_obj = bpy.data.objects[prev_sample_value] \
                    if prev_sample_value else None
            if obj == prev_obj:
                continue
            obj_name = f'{obj.name}' if obj else obj
            self.ray_cast[sample] = obj_name
            if prev_obj: changed_subjects.append(prev_obj)
            if obj: changed_subjects.append(obj)
        if changed_subjects:
            self.write_ray_cast()
        return list(set(changed_subjects))

    def set_cam_for_style(self, style: str) -> None:
        """ Prepare camera for creating lineart according to chosen style """
        if drawing_style == 'c':
            self.obj.data.clip_end = self.clip_start + .01
        if drawing_style == 'b':
            self.__get_cam_data()
            self.obj.matrix_world = (self.translate_matrix @ self.matrix) @ \
                    self.inverse_matrix
    
    def restore_cam(self) -> None:
        """ Restore orginal camera values """
        self.obj.data.clip_end = self.clip_end
        self.obj.matrix_world = self.matrix

class Drawing_context:
    args: list[str]
    style: str
    selected_subjects: list[bpy.types.Object]
    subjects: list[bpy.types.Object]
    camera: Drawing_camera 
    depsgraph: bpy.types.Depsgraph
    frame_size: float ## tuple[float, float] ... try?


    DEFAULT_STYLE: str = 'pc'
    RENDER_BASEPATH: str = bpy.path.abspath(bpy.context.scene.render.filepath)
    RENDER_RESOLUTION_X: int = bpy.context.scene.render.resolution_x
    RENDER_RESOLUTION_Y: int = bpy.context.scene.render.resolution_y

    def __init__(self, args: list[str]):
        self.args = args
        self.style = self.__get_style()
        self.depsgraph = bpy.context.evaluated_depsgraph_get()
        self.depsgraph.update()
        selection = self.__get_objects()
        self.selected_subjects = selection['objects']
        self.drawing_camera = Drawing_camera(selection['camera'], self)
        self.frame_size = self.drawing_camera.obj.data.ortho_scale

        if not self.selected_subjects:
            print("Scan for visible objects...")
            scanning_start_time = time.time()
            self.drawing_camera.scan_all()
            scanning_time = time.time() - scanning_start_time
            print('scan samples\n', self.drawing_camera.checked_samples)
            print(f"   ...scanned in {scanning_time} seconds")
        else:
            print("Scan for visibility of objects...")
            scanning_start_time = time.time()
            for obj in self.selected_subjects:
                subj = Drawing_subject(obj, self)
                ## Scan samples of previous position
                self.drawing_camera.scan_previous_obj_area(subj.name)
                ## Scan subj 
                self.drawing_camera.scan_object_area(subj)
            print('scan samples\n', self.drawing_camera.checked_samples)
            scanning_time = time.time() - scanning_start_time
            print(f"   ...scanned in {scanning_time} seconds")
        self.subjects = self.drawing_camera.objects_to_draw
        print('subjects', self.subjects)

        self.svg_size = format_svg_size(self.frame_size * 10, 
                self.frame_size * 10)
        self.svg_factor = self.frame_size/self.RENDER_RESOLUTION_X * \
                RESOLUTION_FACTOR
        self.svg_styles = [prj.STYLES[d_style]['name'] for d_style in 
                self.style]

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
        return {'objects': objs, 'camera': cam}
        
class Draw_maker:
    draw_context: Drawing_context

    def __init__(self, draw_context):
        self.drawing_context = draw_context
        self.drawing_camera = draw_context.drawing_camera

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context
    
    def export_grease_pencil(self, grease_pencil: bpy.types.Object, 
            remove: bool, svg_suffix: str = '') -> str:
        """ Export grease_pencil to svg and return its path """
        prj_utils.make_active(grease_pencil)

        svg_path = self.subject.get_svg_path(suffix=svg_suffix)
        bpy.ops.wm.gpencil_export_svg(filepath=svg_path, 
                selected_object_type='VISIBLE')
        if remove:
            bpy.data.objects.remove(grease_pencil, do_unlink=True)
        return self.subject.svg_path

    def __create_lineart_grease_pencil(self, drawing_style: str) \
            -> bpy.types.Object:
        """ Create a grease pencil with lineart modifier according to 
            drawing_style """
        draw_subject = self.subject
        if not draw_subject:
            return None
        lineart_gp = prj_utils.create_lineart(source=self.subject, 
            style=drawing_style, la_source=draw_subject)
        ## Hide grease pencil line art to keep next calculations fast
        #lineart_gp.hide_viewport = True
        return lineart_gp

    def draw(self, subject: 'Drawing_subject', draw_style: str, 
            remove: bool = True) -> list[str]:
        """ Create a grease pencil for subject and add a lineart modifier for
            every draw_style. 
            Then export the grease pencil and return its filepath """
        self.subject = subject
        svg_paths = []
        for drawing_style in draw_style:
            file_suffix = prj.STYLES[drawing_style]['name']
            self.drawing_camera.set_cam_for_style(drawing_style)
            lineart_gp = self.__create_lineart_grease_pencil(drawing_style)
            if not lineart_gp: 
                continue
            #lineart_gp.hide_viewport = False
            svg_paths.append(self.export_grease_pencil(
                lineart_gp, remove, file_suffix))
            self.drawing_camera.restore_cam()
        return svg_paths


class Drawing_subject:
    obj: bpy.types.Object
    drawing_context: Drawing_context
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    svg_path: str

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
        self.grease_pencil = None

    def set_drawing_context(self, draw_context: Drawing_context) -> None:
        self.drawing_context = draw_context

    def get_drawing_context(self) -> Drawing_context:
        return self.drawing_context

    def get_svg_path(self, prefix = None, suffix = None) -> str:
        """ Return the svg filepath with prefix or suffix """
        path = self.drawing_context.RENDER_BASEPATH
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        self.svg_path = f"{path}{sep}{pfx}{self.obj.name}{sfx}.svg"
        return self.svg_path
