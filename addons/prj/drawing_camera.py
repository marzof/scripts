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
import ast
import numpy as np
import math
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
from prj.scanner import Scanner
from prj.checked_sample import Checked_sample, checked_samples
from prj.event import subscribe, post_event
import time

SCANNING_STEP: float = .1
RAY_CAST_FILENAME: str = 'ray_cast'
BASE_ROUNDING: int = 6

def range_2d(area: tuple[tuple[float]], step: float) -> list[tuple[float]]:
    """ Get a list representing a 2-dimensional array covering the area 
        by step interval """
    x_min, x_max = area[0][0], area[1][0] + step
    y_min, y_max = area[0][1], area[1][1] + step

    print("Get scanning range...")
    scanning_start_time = time.time()
    samples = [(round(x, BASE_ROUNDING), round(y, BASE_ROUNDING)) \
            for y in np.arange(y_min, y_max, step) 
            for x in np.arange(x_min, x_max, step)]
    scanning_time = time.time() - scanning_start_time
    print(f"   ...got in {scanning_time} seconds")
    return samples

def round_to_base(x: float, base: float, round_func, 
        rounding: int = BASE_ROUNDING) -> float:
    """ Use rounding function to round x to base (for instance: 
        x = 4.77, base = 0.5, round_func = math.floor -> return 4.5 ) """
    return round(base * round_func(x / base), rounding)

def get_obj_bound_box_from_cam_view(obj: bpy.types.Object, 
        camera: bpy.types.Object, matrix: Matrix = None) -> list[Vector]:
    """ Get object bounding box relative to camera frame"""
    if not matrix:
        matrix = obj.matrix_world
    world_obj_bbox = [matrix @ Vector(v) for v in obj.bound_box]
    bbox_from_cam_view = [world_to_camera_view(bpy.context.scene, 
        camera, v) for v in world_obj_bbox]
    return bbox_from_cam_view

def frame_obj_bound_rect(obj: bpy.types.Object, camera: bpy.types.Object, 
        matrix: Matrix = None, round_up: float = None) -> dict[str,float]:
    """ Get the bounding rect of obj in cam view coords  """
    depsgraph = bpy.context.evaluated_depsgraph_get()
    bound_box = get_obj_bound_box_from_cam_view(obj, camera, matrix)
    bbox_xs = [v.x for v in bound_box]
    bbox_ys = [v.y for v in bound_box]
    bbox_zs = [v.z for v in bound_box]
    x_min, x_max = max(0.0, min(bbox_xs)), min(1.0, max(bbox_xs))
    y_min, y_max = max(0.0, min(bbox_ys)), min(1.0, max(bbox_ys))
    if x_min > 1 or x_max < 0 or y_min > 1 or y_max < 0:
        ## obj is out of frame
        return None
    if round_up:
        x_min_round = round_to_base(x_min, round_up, math.floor)
        x_max_round = round_to_base(x_max, round_up, math.ceil)
        y_min_round = round_to_base(y_min, round_up, math.floor)
        y_max_round = round_to_base(y_max, round_up, math.ceil)
        result = {'x_min': x_min_round, 'y_min': y_min_round, 
                'x_max': x_max_round, 'y_max': y_max_round}
        return result
    return {'x_min': x_min, 'y_min': y_min, 'x_max': x_max, 'y_max': y_max}

def get_obj_area_samples(obj: 'bpy.types.Object', cam: 'bpy.types.Object', 
        scanning_step: float, matrix: Matrix = None):
    """ Return samples grid (at scanning_step interval) for obj area """
    scan_limits = frame_obj_bound_rect(obj, cam, matrix, scanning_step)
    area_to_scan = ((scan_limits['x_min'], scan_limits['y_min']), 
            (scan_limits['x_max'], scan_limits['y_max']))
    print('area to scan', area_to_scan)
    if not area_to_scan:
        return None
    area_samples = range_2d(area_to_scan, scanning_step)
    return area_samples

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
    ray_cast: dict[tuple[float], Checked_sample]
    clip_start: float
    clip_end: float
    matrix: Matrix
    objects_to_draw: list[Checked_sample]
    visible_objects: list[Checked_sample]

    def __init__(self, camera: bpy.types.Object, 
            draw_context: 'Drawing_context'):
        self.obj = camera
        self.name = camera.name
        self.drawing_context = draw_context
        working_scene = self.drawing_context.working_scene
        working_scene.collection.objects.link(self.obj)
        working_scene.camera = self.obj
        self.scanner = Scanner(draw_context.depsgraph, self, SCANNING_STEP)
        self.path = self.get_path()
        self.direction = camera.matrix_world.to_quaternion() @ \
                Vector((0.0, 0.0, -1.0))
        self.ortho_scale = camera.data.ortho_scale
        self.clip_start = camera.data.clip_start
        self.clip_end = camera.data.clip_end
        self.matrix = camera.matrix_world
        self.local_frame = [v * Vector((1,1,self.clip_start)) 
                for v in camera.data.view_frame()]
        self.frame = [camera.matrix_world @ v for v in self.local_frame]
        self.frame_origin = self.frame[2]
        self.frame_x_vector = self.frame[1] - self.frame[2]
        self.frame_y_vector = self.frame[0] - self.frame[1]
        self.frame_z_start = -camera.data.clip_start

        self.ray_cast_filepath = os.path.join(self.path, RAY_CAST_FILENAME)
        print("Get ray cast data...")
        scanning_start_time = time.time()
        self.ray_cast = self.get_ray_cast_data()
        scanning_time = time.time() - scanning_start_time
        print(f"   ...got in {scanning_time} seconds")

        self.inverse_matrix = Matrix().Scale(-1, 4, (.0,.0,1.0))
        self.objects_to_draw = []
        self.visible_objects = []
        subscribe('scanned_area', self.analyze_samples)
        subscribe('scanned_area', self.update_ray_cast)
        subscribe('analyzed_data', self.update_visible_objects)
        subscribe('analyzed_data', self.update_objects_to_draw)
        subscribe('updated_ray_cast', self.write_ray_cast)

    def update_objects_to_draw(self, 
            scan_result: dict[str, list['Instance_object']]) -> None:
        changed_objects = scan_result['changed_objects']
        new_objects_to_draw = [obj for obj in changed_objects 
                if obj not in self.objects_to_draw]
        self.objects_to_draw += new_objects_to_draw

    def update_visible_objects(self, 
            scan_result: dict[str, list['Instance_object']]) -> None:
        visible_objects = scan_result['visible_objects']
        new_visible_objects = [obj for obj in visible_objects
                if obj not in self.visible_objects]
        self.visible_objects += new_visible_objects

    def update_ray_cast(self, samples:list[Checked_sample]) -> None:
        prev_ray_cast = self.ray_cast.copy()
        for sample in samples:
            self.ray_cast[sample.coords] = sample.content
        if self.ray_cast != prev_ray_cast:
            post_event('updated_ray_cast')

    def get_path(self) -> str:
        """ Return folder path named after camera (create it if needed) """
        cam_path = os.path.join(self.drawing_context.RENDER_BASEPATH, self.name)
        try:
            os.mkdir(cam_path)
        except OSError:
            print (f'{cam_path} already exists. Going on')
        return cam_path

    def scan_all(self) -> None:
        """ Scan all the camera frame """
        area_to_scan = ((0.0, 0.0), (1.0, 1.0))
        area_samples = range_2d(area_to_scan, self.scanner.step)
        self.scan_area(area_samples)

    def quick_scan_obj(self, obj: bpy.types.Object, matrix: Matrix = None, 
            scanning_step: float = None) -> bool:
        """ Scan the obj area, update checked_samples and get if obj is found """
        if not scanning_step:
            scanning_step = self.scanner.step
        if not matrix:
            matrix = obj.matrix_world

        area_samples = get_obj_area_samples(obj, self.obj, scanning_step, matrix)
        if not area_samples:
            return
        new_samples = [sample for sample in area_samples \
                if sample not in checked_samples]
        scan_result = self.scanner.scan_area_for_target(new_samples, self, obj)
        samples_result = scan_result['samples']
        sample_objects = []
        for sample in samples_result:
            if samples_result[sample]:
                obj = samples_result[sample]['object'] 
                matrix = samples_result[sample]['matrix'].copy()
            else:
                obj, matrix = None, None
            sample_objects.append(Checked_sample(coords=sample, obj=obj, 
                matrix=matrix))

        if sample_objects:
            post_event('scanned_area', sample_objects)
        return scan_result['result']

    def scan_object_area(self, obj: bpy.types.Object) -> None:
        """ Scan the area of subj """
        area_samples = get_obj_area_samples(obj, self.obj, self.scanner_step)
        if area_samples:
            area_samples = range_2d(area_to_scan, self.scanner_step)
            self.scan_area(area_samples)

    def scan_previous_obj_area(self, obj_name: str) -> None:
        """ Scan the area where obj was """
        samples = []
        for sample, obj_str in self.ray_cast.items():
            if obj_str == obj_name:
               samples.append(sample)
        self.scan_area(samples)

    def scan_area(self, area_samples: list[tuple[float]]) -> None:
        """ Scan area_samples and collect result into Checked_sample objects """
        new_samples = [sample for sample in area_samples \
                if sample not in checked_samples]
        samples_result = self.scanner.scan_area(new_samples, self)
        sample_objects = []
        for sample in samples_result:
            if samples_result[sample]:
                obj = samples_result[sample]['object'] 
                matrix = samples_result[sample]['matrix'].copy()
            else:
                obj, matrix = None, None
            sample_objects.append(Checked_sample(coords=sample, obj=obj, 
                matrix=matrix))

        post_event('scanned_area', sample_objects)

    def get_visible_objects(self) -> list[bpy.types.Object]:
        return self.visible_objects

    def get_objects_to_draw(self) -> list[bpy.types.Object]:
        """ Add selected object (instance objects) to objects_to_draw and 
            return objects_to_draw """
        return self.objects_to_draw

    def set_objects_to_draw(self, objs: list[bpy.types.Object]) -> \
            list[bpy.types.Object]:
        self.objects_to_draw = objs
        return self.objects_to_draw

    def get_ray_cast_data(self) -> dict[tuple[float], Checked_sample]:
        """ Get data (in a dictionary) from ray_cast file if it exists 
            (or creates it if missing )"""
        data = {}
        try:
            with open(self.ray_cast_filepath) as f:
                for line in f:
                    raw_sample = ast.literal_eval(line)
                    raw_coords = raw_sample[0]
                    raw_content = raw_sample[1]
                    obj_name = raw_content['object']
                    library_filepath = raw_content['library']
                    obj = None if not raw_content['object'] else \
                            bpy.data.objects[obj_name, library_filepath]
                    matrix = None if not raw_content['matrix'] else \
                            Matrix(raw_content['matrix']).copy()
                    sample_object = Checked_sample(coords=raw_coords, obj=obj,
                            matrix=matrix, collect=False)
                    data[raw_coords] = sample_object.content
                    #data[raw_coords] = sample_object.instance_object
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
                f.write(f'{sample}, {value}\n')

    def analyze_samples(self, samples:list[Checked_sample]) -> None:
        """ Compare samples with ray_cast data and get the dict:
            {'changed_objects': list[Instance_object],
            'visible_objects': list[Instance_object]} """
        changed_objects, visible_objects = [], []
        for sample in samples:
            instance = None if not sample.obj else sample.instance_object
            if instance and instance not in visible_objects:
                visible_objects.append(instance)
            
            prev_sample_content = self.ray_cast[sample.coords] \
                    if sample.coords in self.ray_cast else None
            if prev_sample_content and not prev_sample_content.is_none:
                prev_instance = prev_sample_content.get_instance_object()
            else:
                prev_instance = None
            if not instance and not prev_instance:
                continue
            if instance and instance.is_same_content_as(prev_instance):
                continue
            if prev_instance and prev_instance not in changed_objects:
                changed_objects.append(prev_instance)
            if instance and instance not in changed_objects:
                changed_objects.append(instance)

        result = {'changed_objects': changed_objects,
                'visible_objects': visible_objects}
        post_event('analyzed_data', result)

    def __get_translate_matrix(self) -> Matrix:
        """ Get matrix for move camera towards his clip_start """
        normal_vector = Vector((0.0, 0.0, -2 * self.clip_start))
        z_scale = round(self.matrix.to_scale().z, BASE_ROUNDING)
        opposite_matrix = Matrix().Scale(z_scale, 4, (.0,.0,1.0))
        base_matrix = self.matrix @ opposite_matrix
        translation = base_matrix.to_quaternion() @ (normal_vector * z_scale)
        return Matrix.Translation(translation)

    def reverse_cam(self, style: str) -> None:
        """ Inverse camera matrix for back views """
        self.obj.matrix_world = (self.__get_translate_matrix() @ \
                self.matrix) @ self.inverse_matrix

    def restore_cam(self) -> None:
        """ Restore orginal camera values """
        #self.obj.data.clip_end = self.clip_end
        self.obj.matrix_world = self.matrix

