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
import math
from mathutils import Vector
from prj.utils import point_in_quad, flatten
from prj.drawing_camera import get_drawing_camera
from prj.svg_path import Svg_path
from prj.working_scene import get_working_scene
from bpy_extras.object_utils import world_to_camera_view

libraries = []

def to_hex(c: float) -> str:
    """ Return srgb hexadecimal version of c """
    if c < 0.0031308:
        srgb = 0.0 if c < 0.0 else c * 12.92
    else:
        srgb = 1.055 * math.pow(c, 1.0 / 2.4) - 0.055
    return hex(max(min(int(srgb * 255 + 0.5), 255), 0))

f_to_8_bit = lambda c: int(hex(int(c * 255)),0)

def frame_obj_bound_rect(cam_bound_box: list[Vector]) -> dict[str, float]:
    """ Get the bounding rect of obj in cam view coords  """
    bbox_xs = [v.x for v in cam_bound_box]
    bbox_ys = [v.y for v in cam_bound_box]
    bbox_zs = [v.z for v in cam_bound_box]
    x_min, x_max = max(0.0, min(bbox_xs)), min(1.0, max(bbox_xs))
    y_min, y_max = max(0.0, min(bbox_ys)), min(1.0, max(bbox_ys))
    if x_min > 1 or x_max < 0 or y_min > 1 or y_max < 0:
        ## obj is out of frame
        return None
    return {'x_min': x_min, 'y_min': y_min, 'x_max': x_max, 'y_max': y_max}

def unfold_ranges(ranges: list[tuple[int]]) -> list[int]:
    """ Flatten ranges in a single list of value """
    result = []
    for r in ranges:
        if len(r) == 1:
            result += [r[0]]
            continue
        result += list(range(r[0], r[1]+1))
    return result

class Drawing_subject:
    obj: bpy.types.Object
    bounding_rect: list[Vector]
    overlapping_subjects: list['Drawing_subject']
    previous_pixels_subjects: list['Drawing_subject']
    is_cut: bool
    lineart: bpy.types.Object ## bpy.types.GreasePencil
    working_scene: 'Working_scene'
    svg_path: Svg_path
    render_pixels: list[int]
    previous_render_pixels: list[int]
    pixels_range: list[tuple[int]]  ## Exery tuple define the start and the end
                                    ## (end included!) of pixels's render lines 

    FULL_NAME_SEP: str = '_-_'

    def __init__(self, eval_obj: bpy.types.Object, name: str, 
            mesh: bpy.types.Mesh, matrix: 'mathutils.Matrix', 
            parent: bpy.types.Object, is_instance: bool, 
            library: bpy.types.Library, cam_bound_box: list[Vector], 
            is_in_front: bool, is_behind: bool):
        print('Create subject for', name)
        self.eval_obj = eval_obj
        self.name = name
        self.mesh = mesh
        self.matrix = matrix
        self.parent = parent
        self.full_name = f"{self.parent.name}{self.FULL_NAME_SEP}{self.name}" \
                if self.parent else name
        self.is_instance = is_instance
        self.library = library
        self.cam_bound_box = cam_bound_box
        if self.library and self.library not in libraries:
            libraries.append(self.library)
        self.overlapping_subjects = []
        self.previous_pixels_subjects = []
        self.bounding_rect = []
        self.render_pixels = []
        self.pixels_range = []
        self.render_resolution = []

        svg_path_args = {'main': True}
        ## Move a no-materials duplicate to working_scene: materials could 
        ## bother lineart (and originals are kept untouched)
        self.working_scene = get_working_scene()
        obj_name = self.full_name
        self.obj = bpy.data.objects.new(name=obj_name, object_data=self.mesh)
        self.obj.matrix_world = self.matrix
        self.obj.data.materials.clear()
        self.working_scene.link_object(self.obj)

        self.is_in_front = is_in_front
        self.is_behind = is_behind
        self.is_cut = self.is_in_front and self.is_behind

        self.svg_path = Svg_path(path=self.get_svg_path(**svg_path_args))
        self.svg_path.add_object(self)
        try:
            prev_svg = open(self.svg_path.path, 'r')
            prev_svg_content = prev_svg.read()
            prev_svg.close()
            self.previous_svg = prev_svg_content
            svg_lines = self.previous_svg.split(os.linesep)
            prev_render_pixels = ast.literal_eval(svg_lines[-2])
            self.previous_render_pixels = unfold_ranges(prev_render_pixels)
        except OSError:
            print (f"{self.svg_path.path} doesn't exists")
            self.previous_svg = None
            self.previous_render_pixels = None

        self.collections = [coll.name for coll in self.obj.users_collection \
                if coll is not bpy.context.scene.collection]
        self.type = self.obj.type
        self.lineart_source_type = 'OBJECT'
        self.grease_pencil = None

    def __repr__(self) -> str:
        return f'Drawing_subject[{self.name}]'

    def set_color(self, rgba: tuple[float]) -> None:
        """ Assign rgba color to object """
        r, g, b, a = rgba
        self.obj.color = rgba
        #self.color = (int(to_hex(r),0), int(to_hex(g),0), int(to_hex(b),0),
        #        int(to_hex(a),0))
        self.color = (f_to_8_bit(r), f_to_8_bit(g), f_to_8_bit(b), f_to_8_bit(a))

    def get_svg_path(self, main: bool = False, 
            prefix: str = None, suffix: str = None) -> None:
        """ Return the svg filepath with prefix or suffix """
        drawing_camera = get_drawing_camera()
        path = drawing_camera.path
        sep = "" if path.endswith(os.sep) else os.sep
        pfx = f"{prefix}_" if prefix else ""
        sfx = f"_{suffix}" if suffix else ""
        svg_path = f"{path}{sep}{pfx}{self.full_name}{sfx}.svg"
        return svg_path

    def set_grease_pencil(self, gp: bpy.types.Object) -> None:
        self.grease_pencil = gp
    
    def get_bounding_rect(self) -> None:
        """ Get the bounding rectangle from camera view """
        bounding_rect = frame_obj_bound_rect(self.cam_bound_box)
        verts = [Vector((bounding_rect['x_min'], bounding_rect['y_min'])),
                Vector((bounding_rect['x_max'], bounding_rect['y_min'])),
                Vector((bounding_rect['x_max'], bounding_rect['y_max'])),
                Vector((bounding_rect['x_min'], bounding_rect['y_max']))]
        self.bounding_rect = verts

    def add_overlapping_subj(self, subject: 'Drawing_subject') -> None:
        """ Add subject to self.overlapping_subjects """
        if subject != self and subject not in self.overlapping_subjects:
            self.overlapping_subjects.append(subject)

    def add_overlapping_subjs(self, subjects: list['Drawing_subject']) -> None:
        """ Add subjects (list) to self.overlapping_subjects """
        for subj in subjects:
            self.add_overlapping_subj(subj)

    def add_prev_pixels_subject(self, subj: 'Drawing_subject') -> None:
        """ Add subj to self.previous_pixels_subjects """
        if subj != self and subj not in self.previous_pixels_subjects:
            self.previous_pixels_subjects.append(subj)

    def add_prev_pixels_subjects(self, 
            subjects: list['Drawing_subject']) -> None:
        """ Add subjects (list) to self.previous_pixels_subjects """
        for subj in subjects:
            self.add_prev_pixels_subject(subj)

    def get_overlap_subjects(self, subjects: list['Drawing_subject']) -> None:
        """ Populate self.overlapping_subjects with subjects that overlaps in
            frame view and add self to those subjects too """
        for subject in subjects:
            if subject == self:
                continue
            if subject in self.overlapping_subjects:
                continue
            for vert in self.bounding_rect:
                if point_in_quad(vert, subject.bounding_rect):
                    self.add_overlapping_subj(subject)
                    break
            for vert in subject.bounding_rect:
                if point_in_quad(vert, self.bounding_rect):
                    self.add_overlapping_subj(subject)
                    break

    def set_resolution(self, resolution: int) -> None:
        self.render_resolution = resolution

    def get_area_pixels(self) -> list[int]:
        """ Get the pixel number (int) of the subject bounding rect area """
        resolution = self.render_resolution
        bound_rect_x = self.bounding_rect[0].x
        bound_rect_y = self.bounding_rect[2].y
        bound_width = self.bounding_rect[2].x - self.bounding_rect[0].x
        bound_height = self.bounding_rect[2].y - self.bounding_rect[0].y
        px_from_x = math.floor(resolution * bound_rect_x)
        px_from_y = resolution - math.ceil(resolution * bound_rect_y)
        px_width = math.ceil(resolution * bound_width)
        px_height = math.ceil(resolution * bound_height)
        pixels = flatten([list(range(px_from_x+(resolution*y), 
            px_from_x+(resolution*y)+px_width))
            for y in range(px_from_y, px_from_y + px_height)])
        return pixels

    def update_render_pixels(self, render_pixels: 'ImagingCore') -> None:
        """ For the area of subject check if pixels are blank or filled 
            and populate render_pixels """
        area_pixels = self.get_area_pixels()
        for pixel in area_pixels:
            if render_pixels[pixel][3] != 255:
                continue
            self.render_pixels.append(pixel)

    def add_render_pixel(self, pixel: int) -> None:
        """ Collect all the pixels where the subject actually appears 
            Pixels are stored individually and in range """

        if len(self.render_pixels) == 1:
            self.pixels_range = [(pixel,)]
        elif (pixel-1) == self.pixels_range[-1][-1]:
            self.pixels_range[-1] = (self.pixels_range[-1][0], pixel)
        else:
            self.pixels_range.append((pixel,))

    def remove(self):
        self.working_scene.unlink_object(self.obj)
        bpy.data.objects.remove(self.obj, do_unlink=True)

