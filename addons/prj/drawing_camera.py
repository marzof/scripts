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
from mathutils import Vector, Matrix #, geometry
import prj
from prj.drawing_subject import Drawing_subject
from prj.scanner import Scanner
from prj.utils import get_obj_bound_box

def range_2d(area: tuple[tuple[float]], step: float) -> list[tuple[float]]:
    """ Get a list representing a 2-dimensional array covering the area 
        by step interval """
    x_min, x_max = area[0][0], area[1][0] + step
    y_min, y_max = area[0][1], area[1][1] + step
    samples = [(round(x, prj.BASE_ROUNDING), round(y, prj.BASE_ROUNDING)) \
            for y in np.arange(y_min, y_max, step) 
            for x in np.arange(x_min, x_max, step)]
    return samples

def round_to_base(x: float, base: float, round_func, 
        rounding: int = prj.BASE_ROUNDING) -> float:
    """ Use rounding function to round x to base (for instance: 
        x = 4.77, base = 0.5, round_func = math.floor -> return 4.5 ) """
    return round(base * round_func(x / base), rounding)


#########################
subscribers = dict()

def subscribe(event_type: str, fn):
    if not event_type in subscribers:
        subscribers[event_type] = []
    subscribers[event_type].append(fn)

def post_event(event_type: str, data):
    print('event data',data)
    if not event_type in subscribers:
        return
    for fn in subscribers[event_type]:
        fn(data)
#########################


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
    clip_start: float
    clip_end: float
    matrix: Matrix

    def __init__(self, camera: bpy.types.Object, 
            draw_context: 'Drawing_context'):
        self.obj = camera
        self.name = camera.name
        self.drawing_context = draw_context
        self.scanner = Scanner(draw_context.depsgraph, self, prj.SCANNING_STEP)
        self.path = self.get_path()
        self.direction = camera.matrix_world.to_quaternion() @ \
                Vector((0.0, 0.0, -1.0))
        self.frame = [camera.matrix_world @ v for v in camera.data.view_frame()]
        self.frame_origin = self.frame[2]
        self.frame_x_vector = self.frame[1] - self.frame[2]
        self.frame_y_vector = self.frame[0] - self.frame[1]
        self.frame_z_start = -camera.data.clip_start

        self.ray_cast_filepath = os.path.join(self.path, prj.RAY_CAST_FILENAME)
        self.ray_cast = self.get_ray_cast_data()
        self.checked_samples = {}

        self.clip_start = camera.data.clip_start
        self.clip_end = camera.data.clip_end
        self.matrix = camera.matrix_world
        self.inverse_matrix = Matrix().Scale(-1, 4, (.0,.0,1.0))
        subscribe('scanned_area', self.update_data)
    
    ## TODO check if is it possible to avoid store visible objs and objs to draw
    def update_data(self, samples: dict[tuple[float], bpy.types.Object]) -> None:
        """ Update checked_samples, objects_to_draw, visible_objects """
        for sample in samples:
            self.checked_samples[sample] = samples[sample]
        scan_result = self.__analyze_samples(samples)
        changed_objects = scan_result['changed_objects']
        focused_objects = self.drawing_context.selected_objects + changed_objects
        self.objects_to_draw = list(set(focused_objects))
        self.visible_objects = scan_result['visible_objects']
        self.ray_cast.update(scan_result['changed_ray_cast'])
        if changed_objects:
            self.write_ray_cast()

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
        
    def scan_all(self) -> dict[tuple[float], bpy.types.Object]:
        """ Scan all the camera frame """
        area_to_scan = ((0.0, 0.0), (1.0, 1.0))
        area_samples = range_2d(area_to_scan, self.scanner.step)
        self.scan_area(area_samples)

    def scan_object_area(self, obj: bpy.types.Object) -> \
            dict[tuple[float], bpy.types.Object]:
        """ Scan the area of subj """
        area_to_scan = self.frame_obj_bound_rect(obj)
        print('area to scan', area_to_scan)
        if area_to_scan:
            area_samples = range_2d(area_to_scan, self.scanner.step)
            print('area samples\n', area_samples)
            self.scan_area(area_samples)

    def scan_previous_obj_area(self, obj_name: str) -> \
            dict[tuple[float], bpy.types.Object]:
        """ Scan the area where obj was """
        samples = []
        for sample, obj_str in self.ray_cast.items():
            if obj_str == obj_name:
               samples.append(sample)
        self.scan_area(samples)

    def scan_area(self, area_samples: list[tuple[float]]) -> \
            dict[tuple[float], bpy.types.Object]:
        """ Scan area_samples and return checked_samples 
            (maintaining updated self.checked_samples) """
        new_samples = [sample for sample in area_samples \
                if sample not in self.checked_samples]
        checked_samples = self.scanner.scan_area(new_samples, self)
        post_event('scanned_area', checked_samples)

    def get_visible_objects(self) -> list[bpy.types.Object]:
        return self.visible_objects
    def get_objects_to_draw(self) -> list[bpy.types.Object]:
        return self.objects_to_draw

    def get_ray_cast_data(self) -> dict[tuple[float], str]:
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

    def __analyze_samples(self, samples:dict[tuple[float],bpy.types.Object]) -> \
            dict:
        """ Compare samples with ray_cast data and return changed_objects
            and visible_objects"""
        changed_objects, visible_objects = [], []
        changed_ray_cast = {}
        for sample in samples:
            obj = samples[sample]
            visible_objects.append(obj)
            prev_sample_value = self.ray_cast[sample] \
                    if sample in self.ray_cast else None
            prev_obj = bpy.data.objects[prev_sample_value] \
                    if prev_sample_value else None
            if obj == prev_obj:
                continue
            changed_ray_cast[sample] = obj.name if obj else obj
            changed_objects.append(prev_obj)
            changed_objects.append(obj)
        changed_objects = [obj for obj in list(set(changed_objects)) if obj]
        visible_objects = [obj for obj in list(set(visible_objects)) if obj]
        return {'changed_objects': changed_objects,
                'visible_objects': visible_objects,
                'changed_ray_cast': changed_ray_cast}

    def __get_translate_matrix(self) -> Matrix:
        """ Get matrix for move camera towards his clip_start """
        normal_vector = Vector((0.0, 0.0, -2 * self.clip_start))
        z_scale = round(self.matrix.to_scale().z, prj.BASE_ROUNDING)
        opposite_matrix = Matrix().Scale(z_scale, 4, (.0,.0,1.0))
        base_matrix = self.matrix @ opposite_matrix
        translation = base_matrix.to_quaternion() @ (normal_vector * z_scale)
        return Matrix.Translation(translation)

    def set_cam_for_style(self, style: str) -> None:
        """ Prepare camera for creating lineart according to chosen style """
        if style == 'c':
            self.obj.data.clip_end = self.clip_start + .01
        if style == 'b':
            self.obj.matrix_world = (self.__get_translate_matrix() @ \
                    self.matrix) @ self.inverse_matrix
    
    def restore_cam(self) -> None:
        """ Restore orginal camera values """
        self.obj.data.clip_end = self.clip_end
        self.obj.matrix_world = self.matrix

