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
import re
import ast
import math
from mathutils import Vector
from prj.utils import point_in_quad, flatten, dotdict, to_hex, f_to_8_bit
from prj.utils import frame_obj_bound_rect, unfold_ranges, remove_grease_pencil
from prj.drawing_camera import get_drawing_camera
from prj.drawing_style import drawing_styles
from prj.svg_path import Svg_path
from prj.working_scene import get_working_scene
from bpy_extras.object_utils import world_to_camera_view

drawing_subjects = []

def get_subjects_list():
    return drawing_subjects

def reset_subjects_list():
    global drawing_subjects
    drawing_subjects.clear()
    
class Drawing_subject:
    obj: bpy.types.Object
    bounding_rect: list[Vector]
    overlapping_subjects: list['Drawing_subject']
    previous_pixels_subjects: list['Drawing_subject']
    is_cut: bool
    grease_pencil: bpy.types.Object ## bpy.types.GreasePencil
    working_scene: 'Working_scene'
    svg_path: Svg_path
    render_pixels: list[int]
    previous_render_pixels: list[int]
    pixels_range: list[tuple[int]]  ## Exery tuple define the start and the end
                                    ## (end included!) of pixels's render lines 

    FULL_NAME_SEP: str = '_-_'
    SVG_DATA_RE = re.compile('(?s:.*)<!--\s(.*)\s-->', re.DOTALL)

    def __init__(self, eval_obj: bpy.types.Object, name: str, 
            drawing_context: 'Drawing_context',
            mesh: bpy.types.Mesh, matrix: 'mathutils.Matrix', 
            parent: bpy.types.Object, is_instance: bool, 
            library: bpy.types.Library, cam_bound_box: list[Vector], 
            is_in_front: bool, is_behind: bool, 
            collections: dict[bpy.types.Collection, str],
            symbol_type: str = None):
        print('Create subject for', name)
        self.eval_obj = eval_obj
        self.name = name
        self.drawing_context = drawing_context
        self.render_resolution = drawing_context.render_resolution
        self.xray_drawing = False
        self.draw_outline = False
        self.wire_drawing = False
        self.back_drawing = False
        self.mesh = mesh
        self.matrix = matrix
        self.parent = parent
        self.full_name = f"{self.parent.name}{self.FULL_NAME_SEP}{self.name}" \
                if self.parent else name
        self.is_instance = is_instance
        self.library = library
        self.cam_bound_box = cam_bound_box
        self.overlapping_subjects = []
        self.previous_pixels_subjects = []
        self.bounding_rect = []
        self.render_pixels = []
        self.pixels_range = []
        self.symbol_type = symbol_type

        svg_path_args = {'main': True}
        ## Move a no-materials duplicate to working_scene: materials could 
        ## bother lineart (and originals are kept untouched)
        self.working_scene = get_working_scene()
        self.obj = bpy.data.objects.new(name=self.full_name, 
                object_data=self.mesh)
        self.obj.matrix_world = self.matrix
        self.obj.data.materials.clear()
        self.working_scene.link_object(self.obj)

        self.is_selected = False
        self.is_in_front = is_in_front
        self.is_behind = is_behind
        self.is_cut = self.is_in_front and self.is_behind
        self.styles = [s for s in drawing_styles if drawing_styles[s].default]
        if self.is_cut:
            self.styles.append('c')
        if self.symbol_type:
            self.styles.append('s')

        self.svg_path = Svg_path(path=self.get_svg_path(**svg_path_args))
        self.svg_path.add_object(self)
        self.previous_data = self.__get_previous_data()
        self.previous_render_pixels = None if not self.previous_data \
                else unfold_ranges(self.previous_data['render_pixels'])
        ## Update options with the previous ones
        if self.previous_data:
            self.update_status(selected=self.is_selected, 
                    data=dotdict(self.previous_data))

        self.collections = collections
        self.type = self.obj.type
        self.lineart_source_type = 'OBJECT'
        self.grease_pencil = None
        drawing_subjects.append(self)

    def __get_previous_data(self):
        """ Get data stored in last subject svg """
        try:
            prev_svg = open(self.svg_path.path, 'r')
            prev_svg_content = prev_svg.read()
            prev_svg.close()
            subject_data_search = re.search(self.SVG_DATA_RE, prev_svg_content)
            subject_data = re.search(self.SVG_DATA_RE, prev_svg_content)
            subject_data_raw = subject_data_search.groups(1)[0]
            previous_data = ast.literal_eval(subject_data_raw)
        except OSError:
            print (f"{self.svg_path.path} doesn't exists")
            previous_data = None
        return previous_data

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

    def update_status(self, selected: bool, data, 
            ignore_options: bool= False) -> None:
        """ Update selection status, options and style according to data """
        self.is_selected = selected
        ## Reset selected subject to default status
        if self.is_selected and self.drawing_context.reset_option:
            self.xray_drawing = False
            self.draw_outline = False
            self.wire_drawing = False
            self.back_drawing = False
            if 'h' in self.styles:
                self.styles.remove('h')
            return
        if ignore_options:
            return
        self.xray_drawing = data.xray_drawing
        self.draw_outline = data.draw_outline
        self.wire_drawing = data.wire_drawing
        self.back_drawing = data.back_drawing
        if self.wire_drawing:
            self.styles.append('h')

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
            frame view (by bounding box) and add self to those subjects too """
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

    def get_area_pixels(self) -> list[int]:
        """ Get the pixel number (int) of the subject bounding rect area """
        resolution = self.render_resolution
        bound_rect_x = self.bounding_rect[0].x
        bound_rect_y = self.bounding_rect[2].y
        bound_width = self.bounding_rect[2].x - self.bounding_rect[0].x
        bound_height = self.bounding_rect[2].y - self.bounding_rect[0].y
        px_from_x = math.floor(resolution[0] * bound_rect_x)
        px_from_y = resolution[1] - math.ceil(resolution[1] * bound_rect_y)
        px_width = math.ceil(resolution[0] * bound_width)
        px_height = math.ceil(resolution[1] * bound_height)
        pixels = flatten([list(range(px_from_x+(resolution[0]*y), 
            px_from_x+(resolution[0]*y)+px_width))
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
            self.add_render_pixel(pixel)

    def add_render_pixel(self, pixel: int) -> None:
        """ Collect all the pixels where the subject actually appears 
            Pixels are stored individually and in range """

        if len(self.render_pixels) == 1:
            self.pixels_range = [(pixel,)]
        elif (pixel-1) == self.pixels_range[-1][-1]:
            self.pixels_range[-1] = (self.pixels_range[-1][0], pixel)
        else:
            self.pixels_range.append((pixel,))

    def remove_grease_pencil(self) -> None:
        if self.grease_pencil:
            remove_grease_pencil(self.grease_pencil)
            self.set_grease_pencil(None)

    def remove(self):
        """ Delete subject """
        if self in drawing_subjects:
            drawing_subjects.remove(self)
        self.working_scene.unlink_object(self.obj)
        bpy.data.meshes.remove(self.obj.data)
        self.remove_grease_pencil()
        self.set_grease_pencil(None)

