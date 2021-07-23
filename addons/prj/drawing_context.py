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
import re
from mathutils import Vector, geometry
from bpy_extras.object_utils import world_to_camera_view
import prj
from prj.drawing_subject import Drawing_subject
from prj.drawing_camera import Drawing_camera, SCANNING_STEP 
from prj.drawing_camera import get_obj_bound_box_from_cam_view
from prj.checked_sample import matrix_to_tuple
from prj.instance_object import Instance_object
from prj.cutter import Cutter
import time

UNIT_FACTORS = {'m': 1, 'cm': 100, 'mm': 1000}
DENSE_SCANNING_STEPS = .001
STYLES = {
        'p': {'name': 'prj', 'occlusion_start': 0, 'occlusion_end': 0,
            'chaining_threshold': 0, 'condition': 'is_in_front'},
        'c': {'name': 'cut', 'occlusion_start': 0, 'occlusion_end': 128,
            'chaining_threshold': 0, 'condition': 'is_cut'},
        'h': {'name': 'hid', 'occlusion_start': 1, 'occlusion_end': 128,
            'chaining_threshold': 0, 'condition': 'is_in_front'},
        'b': {'name': 'bak', 'occlusion_start': 0, 'occlusion_end': 128,
            'chaining_threshold': 0, 'condition': 'is_behind'},
        }
is_renderables = lambda obj: (obj.type, bool(obj.instance_collection)) \
        in [('MESH', False), ('CURVE', False), ('EMPTY', True)]

start_time = time.time()

format_svg_size = lambda x, y: (str(x) + 'mm', str(x) + 'mm')
is_selected_inst_collection = lambda inst_coll, sel_colls: inst_coll in sel_colls

## TODO clean up
def is_cut(obj: bpy.types.Object, matrix: 'mathutils.Matrix', 
        cut_verts: list[Vector], cut_normal: Vector) -> bool:
    """ Check if an edge of obj intersect cut_verts quad plane """
    print('Get cut for', obj.name)
    mesh = obj.to_mesh()
    for edge in mesh.edges:
        verts = edge.vertices
        v0 = matrix @ mesh.vertices[verts[0]].co
        v1 = matrix @ mesh.vertices[verts[1]].co
        #print('edge', edge.index)
        #print('\t', v0, v1)
        ## line and plane are extended to find intersection
        intersection =  geometry.intersect_line_plane(
                v0, v1, cut_verts[0], cut_normal)
        if not intersection:
            continue
        point_on_line = geometry.intersect_point_line(intersection, v0, v1)
        distance_from_line = point_on_line[1]
        if not 0 <= distance_from_line <= 1: ## intersection is not on edge
            continue
        point_on_cut_plane = geometry.intersect_point_quad_2d(intersection, 
                cut_verts[0], cut_verts[1], cut_verts[2], cut_verts[3])
        if not point_on_cut_plane:
            continue
        print('It cuts at', intersection)
        obj.to_mesh_clear()
        return True
    obj.to_mesh_clear()
    return False

## TODO too specialized: get more generalized
def get_cam_z_status(bound_box: list[Vector], camera: bpy.types.Object) -> str:
    """ Check if bound_box is cut, inf front or behind camera plane """
    zs = [v.z for v in bound_box]
    z_min, z_max = min(zs), max(zs)
    cut_plane = camera.data.clip_start
    if z_min <= cut_plane <= z_max:
        return 'CUT'
    if cut_plane < z_max:
        return 'IN_FRONT'
    else: ## z_min < cut_plane
        return 'BEHIND'

def is_framed(object_instance: bpy.types.DepsgraphObjectInstance, 
        camera: bpy.types.Object, depsgraph: bpy.types.Depsgraph) -> \
                dict[str, bool]:
    """ Check if (real, not empty) object_instance is viewed from camera """
    inst_obj = object_instance.object
    ## TODO handle better (ok for some curves: e.g. the extruded ones, 
    ##      not custom shapes)
    if inst_obj.type not in ['CURVE', 'MESH']:
        return {'result': None, 'inside_frame': None, 'cam_z_status': None}
    matrix = inst_obj.matrix_world.copy()
    if inst_obj.type == 'CURVE':
        ## Assign a harmless modifier to the curve in order to calculate
        ## its correct bounding box. Then remove the tmp modifier
        tmp_mod = inst_obj.original.modifiers.new("tmp", 'WELD')
        depsgraph.update()
        matrix = inst_obj.original.matrix_world.copy()
        inst_obj.original.modifiers.remove(tmp_mod)
    bound_box = get_obj_bound_box_from_cam_view(inst_obj, camera, matrix)

    cam_z_status = get_cam_z_status(bound_box, camera)
    for v in bound_box:
        ## TODO handle back objects as well (and avoid far objects)
        if 0 <= v.x <= 1 and 0 <= v.y <= 1:
            return {'result': True, 'inside_frame': True, 
                    'cam_z_status': cam_z_status}
    ## Check if camera frame is in bound_box (e.g. inst_obj bigger than frame)
    bound_box_min = bound_box[0]
    bound_box_max = bound_box[-1]
    for frame_x in [0, 1]:
        for frame_y in [0, 1]:
            frame_x_is_in = bound_box_min.x <= frame_x <= bound_box_max.x
            frame_y_is_in = bound_box_min.y <= frame_y <= bound_box_max.y
            if frame_x_is_in and frame_y_is_in:
                return {'result': True, 'inside_frame': False,
                        'cam_z_status': cam_z_status}
    return {'result': False, 'inside_frame': None, 'cam_z_status': cam_z_status}

def get_instances(camera: bpy.types.Object) -> tuple[list[Instance_object]]:
    """ Check for all object instances in scene and return those which are 
        inside camera frame (and limits) as Instance_object(s)"""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    instance_objects = []
    bigger_instances = []
    for obj_inst in depsgraph.object_instances:
        is_in_frame = is_framed(obj_inst, camera, depsgraph)
        if not is_in_frame['result']:
            continue
        ## Create the Instance_object
        obj = obj_inst.object.original
        lib = obj_inst.object.library 
        inst = obj_inst.is_instance
        par = obj_inst.parent
        cam_z = is_in_frame['cam_z_status']
        mat = obj_inst.object.matrix_world.copy().freeze()
        instance = Instance_object(obj=obj, library=lib, is_instance=inst,
                parent=par, cam_z_status=cam_z, matrix=mat)

        if is_in_frame['inside_frame']:
            instance_objects.append(instance)
        else:
            bigger_instances.append(instance)
    return instance_objects, bigger_instances


class Drawing_context:
    RENDER_BASEPATH: str
    RENDER_RESOLUTION_X: int
    RENDER_RESOLUTION_Y: int
    args: list[str]
    draw_all: bool
    timing_test: bool
    style: str
    scan_resolution: dict
    selected_objects: list[bpy.types.Object]
    subjects: list[Drawing_subject]
    camera: Drawing_camera 
    depsgraph: bpy.types.Depsgraph
    frame_size: float ## tuple[float, float] ... try?
    DEFAULT_STYLES: list[str] = ['p', 'c']
    FLAGS: dict[str, str] = {'draw_all': '-a', 'scan_resolution': '-r',
            'timing_test': '-t'}
    RESOLUTION_FACTOR: float = 96.0 / 2.54 ## resolution / inch

    def __init__(self, args: list[str], context):
        self.RENDER_BASEPATH = bpy.path.abspath(context.scene.render.filepath)
        self.RENDER_RESOLUTION_X = context.scene.render.resolution_x
        self.RENDER_RESOLUTION_Y = context.scene.render.resolution_y
        self.working_scene = bpy.data.scenes.new(name='prj')
        self.working_scene.render.resolution_x = self.RENDER_RESOLUTION_X
        self.working_scene.render.resolution_y = self.RENDER_RESOLUTION_Y
        self.working_scene.render.filepath = self.RENDER_BASEPATH
        self.context = context
        self.args = args
        self.draw_all = False
        self.timing_test = False
        self.style = []
        self.scan_resolution = {'value': SCANNING_STEP, 'units': None}
        self.depsgraph = context.evaluated_depsgraph_get()
        self.depsgraph.update()
        object_args = self.__set_flagged_options()
        selection = self.__get_objects(object_args)
        self.selected_objects = selection['objects']
        self.drawing_camera = Drawing_camera(selection['camera'], self)
        self.cutter = Cutter(self)
        self.drawing_camera.scanner.set_step(self.get_scan_step())
        self.frame_size = self.drawing_camera.obj.data.ortho_scale
        self.subjects = self.__get_subjects(self.selected_objects)

        self.svg_size = format_svg_size(self.frame_size * 10, 
                self.frame_size * 10)
        self.svg_factor = self.frame_size/self.RENDER_RESOLUTION_X * \
                self.RESOLUTION_FACTOR
        self.svg_styles = [STYLES[d_style]['name'] for d_style in 
                self.style]

    def get_instances_to_draw_all(self, instances: list[Instance_object]) -> \
            list[Instance_object]:
        self.draw_all = True
        draw_cam = self.drawing_camera
        draw_cam.scan_all()
        visible_objects = draw_cam.get_visible_objects()[:]
        ## Get not found objects and rescan them with a denser step grid
        ## TODO handle behind objects as well
        instances_to_check = [instance for instance in instances 
                if instance not in visible_objects and 
                instance.cam_z_status != 'BEHIND']
        ## TODO get timing for rescan
        for inst in instances_to_check:
            print('Rescan', inst.obj)
            draw_cam.quick_scan_obj(inst.obj, inst.matrix, 
                    DENSE_SCANNING_STEPS)
        instances_to_draw = draw_cam.get_visible_objects()
        return instances_to_draw

    def get_instances_to_draw_selection(self, instances: list[Instance_object]) \
            -> list[Instance_object]:
        ## TODO implement detection of selected_object
        pass
        #    for obj in selected_objects:
        #        self.drawing_camera.scan_previous_obj_area(obj.name)
        #        self.drawing_camera.scan_object_area(obj)
        #    objects_to_draw = self.drawing_camera.get_objects_to_draw()
        #
        ### Add selected_objects in case of not being scanned
        #all_objects_to_draw = list(set(objects_to_draw + self.selected_objects))
        #instances_to_draw = objects_to_instances(all_objects_to_draw, 
        #        self.drawing_camera.obj)
        #for obj in all_objects_to_draw:
        #    print('to instance', obj)
        #for inst in instances_to_draw:
        #    print('to draw', inst)

    def __get_subjects(self, selected_objects: list[bpy.types.Object]) -> \
            list[Drawing_subject]:
        """ Execute scanning to acquire the subjects to draw """
        draw_cam = self.drawing_camera
        all_instances = get_instances(draw_cam.obj)
        instances = all_instances[0]
        bigger_instances = all_instances[1]

        if not selected_objects or self.draw_all:
            instances_to_draw = self.get_instances_to_draw_all(instances)
        else:
            instances_to_draw = self.get_instances_to_draw_selection(instances)

        instances_to_draw += [instance for instance in bigger_instances 
                if instance in draw_cam.get_visible_objects()]
        skipped_instances = [instance for instance in instances 
                if instance not in instances_to_draw]
        cut_verts = draw_cam.frame
        cut_normal = draw_cam.direction
        ## TODO pass to is_cut just obj with bounding box cutting camera frame
        for inst in skipped_instances:
            if inst.cam_z_status == 'CUT':
                obj = inst.obj.evaluated_get(self.depsgraph)
                if is_cut(obj, inst.matrix, cut_verts, cut_normal):
                    instances_to_draw.append(inst)

        subjects = []
        for instance in instances_to_draw:
            subjects.append(Drawing_subject(instance, self))

        return subjects

    def set_scan_resolution(self, raw_resolution: str) -> None:
        """ Set scan_resolution based on raw_resolution arg """
        search = re.search(r'[a-zA-Z]+', raw_resolution)
        if search:
            index = search.span()[0]
            value = float(raw_resolution[:index])
            units = search.group(0).lower()
        else:
            value = float(raw_resolution)
            units = None
        self.scan_resolution = {'value': value, 'units': units}

    def get_scan_step(self) -> float:
        """ Calculate scanning step and return it """
        value = self.scan_resolution['value']
        units = self.scan_resolution['units']
        cam_frame = self.drawing_camera.ortho_scale
        if units:
            factor = UNIT_FACTORS[units]
            return (value /factor) / cam_frame
        return float(value)

    def __set_flagged_options(self) -> list[str]:
        """ Set flagged values from args and return remaining args for 
            getting objects """
        self.draw_all = self.FLAGS['draw_all'] in self.args
        self.timing_test = self.FLAGS['timing_test'] in self.args

        options_idx = []
        flagged_args = [arg for arg in self.args if arg.startswith('-')]
        for arg in flagged_args:
            arg_idx = self.args.index(arg)
            options_idx.append(arg_idx)
            if arg == self.FLAGS['scan_resolution']:
                raw_resolution = self.args[arg_idx + 1]
                self.set_scan_resolution(raw_resolution)
                options_idx.append(arg_idx + 1)
                continue
            self.style += [l for l in arg if l in STYLES]

        if not self.style: 
            self.style = self.DEFAULT_STYLES
        object_args = [arg for idx, arg in enumerate(self.args) \
                if idx not in options_idx]
        return object_args

    def __get_objects(self, object_args: list[str]) -> \
            tuple[list[bpy.types.Object], bpy.types.Object]:
        """ Extract the camera and renderable objects from args or selection """
        args_objs = ''.join(object_args).split(';')
        selected_objs = self.context.selected_objects
        cam = None
        objs = []
        for ob in args_objs:
            if ob and bpy.data.objects[ob].type == 'CAMERA':
                cam = bpy.data.objects[ob]
            elif ob and is_renderables(bpy.data.objects[ob]):
                objs.append(bpy.data.objects[ob])
        got_objs = bool(objs)
        for ob in selected_objs:
            if not cam and ob.type == 'CAMERA':
                cam = ob
            if not got_objs and is_renderables(ob):
                objs.append(ob)
        return {'objects': objs, 'camera': cam}
