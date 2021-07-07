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
from mathutils import Vector, Matrix #, geometry
from bpy_extras.object_utils import world_to_camera_view
from prj.scanner import Scanner
from prj.event import subscribe, post_event
from prj.utils import get_obj_bound_box
from prj.instance_object import Instance_object
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
    ray_cast: dict[tuple[float], Instance_object]
    checked_samples: dict[tuple[float], Instance_object] 
    clip_start: float
    clip_end: float
    matrix: Matrix
    objects_to_draw: list[Instance_object]
    visible_objects: list[Instance_object]

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
        self.checked_samples = {}

        self.inverse_matrix = Matrix().Scale(-1, 4, (.0,.0,1.0))
        self.objects_to_draw = []
        self.visible_objects = []
        subscribe('scanned_area', self.update_checked_samples)
        subscribe('scanned_area', self.analyze_samples)
        subscribe('analyzed_data', self.update_visible_objects)
        subscribe('analyzed_data', self.update_objects_to_draw)
        subscribe('analyzed_data', self.update_ray_cast)
        subscribe('updated_ray_cast', self.write_ray_cast)
    
    def update_checked_samples(self,
            samples: dict[tuple[float], Instance_object]) -> None:
        self.checked_samples.update(samples)

    def get_selected_instances(self) -> list[Instance_object]:
        selected_instances = [inst_obj for inst_obj in self.visible_objects
                if inst_obj.obj in self.drawing_context.selected_objects]
        return selected_instances

    def update_objects_to_draw(self, scan_result: dict) -> None:
        changed_objects = scan_result['changed_objects']
        new_inst_objects_to_draw = [inst_obj for inst_obj in changed_objects 
                if inst_obj not in self.objects_to_draw]
        self.objects_to_draw += new_inst_objects_to_draw

    def update_visible_objects(self, scan_result: dict) -> None:
        visible_objects = scan_result['visible_objects']
        new_visible_inst_objects = [inst_obj for inst_obj in visible_objects
                if inst_obj not in self.visible_objects]
        self.visible_objects += new_visible_inst_objects

    def update_ray_cast(self, scan_result: dict) -> None:
        self.ray_cast.update(scan_result['ray_cast'])
        post_event('updated_ray_cast', bool(scan_result['changed_objects']))

    def get_path(self) -> str:
        """ Return folder path named after camera (create it if needed) """
        cam_path = os.path.join(self.drawing_context.RENDER_BASEPATH, self.name)
        try:
            os.mkdir(cam_path)
        except OSError:
            print (f'{cam_path} already exists. Going on')
        return cam_path

    def frame_obj_bound_rect(self, obj: bpy.types.Object) -> tuple[tuple[float]]:
        """ Get the bounding rect of obj in cam view coords 
            (rect is just greater than object and accords with the step grid) """
        world_obj_bbox = get_obj_bound_box(obj, self.drawing_context.depsgraph)
        bbox_from_cam_view = [world_to_camera_view(bpy.context.scene, 
            self.obj, v) for v in world_obj_bbox]
        bbox_xs = [v.x for v in bbox_from_cam_view]
        bbox_ys = [v.y for v in bbox_from_cam_view]
        bbox_zs = [v.z for v in bbox_from_cam_view]
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

    def scan_object_area(self, obj: bpy.types.Object) -> None:
        """ Scan the area of subj """
        area_to_scan = self.frame_obj_bound_rect(obj)
        print('area to scan', area_to_scan)
        if area_to_scan:
            area_samples = range_2d(area_to_scan, self.scanner.step)
            print('area samples\n', area_samples)
            self.scan_area(area_samples)

    def scan_previous_obj_area(self, obj_name: str) -> None:
        """ Scan the area where obj was """
        samples = []
        for sample, obj_str in self.ray_cast.items():
            if obj_str == obj_name:
               samples.append(sample)
        self.scan_area(samples)

    def scan_area(self, area_samples: list[tuple[float]]) -> None:
        """ Scan area_samples and return checked_samples 
            (maintaining updated self.checked_samples) """
        new_samples = [sample for sample in area_samples \
                if sample not in self.checked_samples]
        checked_samples = self.scanner.scan_area(new_samples, self)
        for sample in checked_samples:
            if checked_samples[sample]:
                obj = checked_samples[sample]['object']
                matrix = checked_samples[sample]['matrix']
                checked_samples[sample] = Instance_object(obj=obj, matrix=matrix)

        post_event('scanned_area', checked_samples)

    def get_visible_objects(self) -> list[bpy.types.Object]:
        return self.visible_objects

    def get_objects_to_draw(self) -> list[bpy.types.Object]:
        for inst in self.get_selected_instances():
            if inst in self.objects_to_draw:
                continue
            self.objects_to_draw.append(inst)
        return self.objects_to_draw

    def get_ray_cast_data(self) -> dict[tuple[float], Instance_object]:
        """ Get data (in a dictionary) from ray_cast file if it exists 
            (or creates it if missing )"""
        data = {}
        try:
            with open(self.ray_cast_filepath) as f:
                for line in f:
                    sample = ast.literal_eval(line)
                    #print('data is', sample)
                    sample_value = None
                    if sample[1]:
                        obj = bpy.data.objects[sample[1]['object']]
                        matrix = Matrix(sample[1]['matrix'])
                        sample_value = Instance_object(obj=obj, matrix=matrix)
                    data[sample[0]] = sample_value
            return data
        except OSError:
            print (f"{self.ray_cast_filepath} doesn't exists. Create it now")
            f = open(self.ray_cast_filepath, 'w')
            f.close()
            return data
    
    def write_ray_cast(self, is_changed: bool) -> None:
        """ Write ray_cast to file if self. ray_cast is_changed"""
        if not is_changed:
            return
        with open(self.ray_cast_filepath, 'w') as f:
            for sample in self.ray_cast:
                value = self.ray_cast[sample] 
                ## Add quotes to actual object name for correct value passing
                f.write(f'{sample}, {value}\n')

    def analyze_samples(self, 
            samples:dict[tuple[float], Instance_object]) -> None:
        """ Compare samples with ray_cast data and get the dict:
            {'changed_objects': list[Instance_object],
            'visible_objects': list[Instance_object],
            'ray_cast': dict[tuple[float], Instance_object]} """
        changed_objects, visible_objects = [], []
        ray_cast = {}
        for sample in samples:
            instance_obj = samples[sample]
            visible_objects.append(instance_obj)
            ray_cast[sample] = instance_obj
            
            prev_sample_value = self.ray_cast[sample] \
                    if sample in self.ray_cast else None
            prev_obj = prev_sample_value.obj if prev_sample_value else None
            if not instance_obj and not prev_obj:
                continue
            if instance_obj and instance_obj.obj == prev_obj:
                continue
            changed_objects.append(prev_sample_value)
            changed_objects.append(instance_obj)

        changed_objects = [inst_obj for inst_obj in list(set(changed_objects)) 
                if inst_obj]
        visible_objects = [inst_obj for inst_obj in list(set(visible_objects)) 
                if inst_obj]
        result = {'changed_objects': changed_objects,
                'visible_objects': visible_objects,
                'ray_cast': ray_cast}
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

