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
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
import prj
from prj.drawing_subject import Drawing_subject
from prj.drawing_camera import Drawing_camera, SCANNING_STEP
from prj.instance_object import Instance_object
from prj.cutter import Cutter
import time

UNIT_FACTORS = {'m': 1, 'cm': 100, 'mm': 1000}
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
    
def is_framed(object_instance: bpy.types.DepsgraphObjectInstance, 
        camera: bpy.types.Object) -> bool:
    """ CHeck if (real) object_instance is viewed from camera """
    inst_obj = object_instance.object
    ## TODO handle better (ok for some curves: e.g. the extruded ones, 
    ##      not custom shapes)
    if inst_obj.type != 'MESH':
    #if not is_renderables(inst_obj) or inst_obj.type == 'EMPTY':
        return
    matrix = inst_obj.matrix_world.copy()
    obj_bound_box = [matrix @ Vector(v) for v in inst_obj.bound_box]
    bbox_from_cam_view = [world_to_camera_view(bpy.context.scene, 
        camera, v) for v in obj_bound_box]
    for v in bbox_from_cam_view:
        is_in = 0 <= v.x <= 1 and 0 <= v.y <= 1
        if is_in:
            return True
    return False

def get_instances(camera: bpy.types.Object):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    instance_objects = []
    for obj_inst in depsgraph.object_instances:
        if not is_framed(obj_inst, camera):
            continue
        obj = obj_inst.object.original
        lib = obj_inst.object.library 
        inst = obj_inst.is_instance
        par = obj_inst.parent
        mat = obj_inst.object.matrix_world.copy().freeze()
        instance = Instance_object(obj=obj, library=lib, is_instance=inst,
                parent=par, matrix=mat)
        instance_objects.append(instance)
        parent_name = instance.parent.name if instance.parent else None
        library = instance.library.filepath if instance.library else 'file'
        obj = obj_inst.object.original
    return instance_objects

def objects_to_instances(objects: list[bpy.types.Object], 
        camera: bpy.types.Object = None) -> list[Instance_object]: 
    """ Convert objects to Instance_object (and check if objects are 
        inside camera frame """
    ## TODO clean up here (two different scopes for one function)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    instance_objects = []
    objs = {obj: obj.instance_collection for obj in objects}
    obj = None

    for obj_inst in depsgraph.object_instances:
        #if not is_framed(obj_inst, camera):
        #    continue
        ## TODO BLOCKING ERROR, to fix:
        ##      multiple instances of same object are not distinguished
        if 'bidet' in obj_inst.object.name or 'Cube' == obj_inst.object.name:
            print(obj_inst.object)
            print('child of', obj_inst.parent)
            print('in scan result + sel', obj_inst.object.original in objs)
            print('is framed', is_framed(obj_inst, camera))
            print(obj_inst.object.matrix_world)

        if obj_inst.object.original in objs:
            obj = obj_inst.object.original
        elif obj_inst.parent and obj_inst.parent.original in objs:
            obj = obj_inst.parent.original
        elif obj_inst.parent and is_selected_inst_collection(
                obj_inst.parent.original.instance_collection, objs.values()):
            obj = obj_inst.parent.original.instance_collection
        else:
            if camera:
                #is_in_frame = is_framed(obj_inst, camera)
                #print(obj_inst.object.name, 'is in camera frame:', is_in_frame)
                continue
            continue

        if obj:
            lib = obj.library 
            inst = obj_inst.is_instance
            par = obj_inst.parent
            mat = obj_inst.object.matrix_world.copy()
            instance = Instance_object(obj=obj, library=lib, is_instance=inst,
                    parent=par, matrix=mat)
            instance_objects.append(instance)
    return instance_objects

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

    def __get_subjects(self, selected_objects: list[bpy.types.Object]) -> \
            list[Drawing_subject]:
        """ Execute scanning to acquire the subjects to draw """
        #if not selected_objects or self.draw_all:
        #    self.draw_all = True
        #    self.drawing_camera.scan_all()
        #    objects_to_draw = self.drawing_camera.get_visible_objects()
        #else:
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
        instances_to_draw = get_instances(self.drawing_camera.obj)
        #raise Exception('Stop here')

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
