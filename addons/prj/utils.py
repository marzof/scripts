#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy, bmesh
from mathutils import Matrix, Vector, geometry
from bpy_extras.object_utils import world_to_camera_view
import prj.drawing_context
import time

GREASE_PENCIL_PREFIX = 'prj_'
GREASE_PENCIL_LAYER = 'prj_lay'
GREASE_PENCIL_MAT = 'prj_mat'
GREASE_PENCIL_MOD = 'prj_la'

def add_line_art_mod(gp: bpy.types.Object, source: bpy.types.Object, 
        source_type: str, style: str) -> None:
    """ Add a line art modifier to gp from source of the source_type 
    with style """

    STYLES = prj.drawing_context.STYLES
    gp_layer = gp.data.layers.new(STYLES[style]['name'])
    gp_layer.frames.new(1)
    gp_mat_name = GREASE_PENCIL_MAT + '_' + STYLES[style]['name']
    if gp_mat_name not in bpy.data.materials:
        gp_mat = bpy.data.materials.new(gp_mat_name)
    else:
        gp_mat = bpy.data.materials[gp_mat_name]
    if not gp_mat.is_grease_pencil:
        bpy.data.materials.create_gpencil_data(gp_mat)
    gp.data.materials.append(gp_mat)

    ## Create and setup lineart modifier
    gp_mod_name = GREASE_PENCIL_MOD + '_' + STYLES[style]['name']
    gp.grease_pencil_modifiers.new(gp_mod_name, 'GP_LINEART')
    gp_mod = gp.grease_pencil_modifiers[gp_mod_name]
    gp_mod.target_layer = gp_layer.info
    gp_mod.target_material = gp_mat
    gp_mod.chaining_image_threshold = STYLES[style]['chaining_threshold']
    gp_mod.use_multiple_levels = True
    gp_mod.use_remove_doubles = True
    gp_mod.use_clip_plane_boundaries = False
    gp_mod.level_start = STYLES[style]['occlusion_start']
    gp_mod.level_end = STYLES[style]['occlusion_end']
    gp_mod.source_type = source_type
    if source_type == 'OBJECT':
        gp_mod.source_object = source
    elif source_type == 'COLLECTION':
        gp_mod.source_collection = source

def create_grease_pencil(name: str, scene: bpy.types.Scene) -> bpy.types.Object:
    """ Create a grease pencil """
    gp = bpy.data.grease_pencils.new(name)

    gp_layer = gp.layers.new(GREASE_PENCIL_LAYER)
    gp_layer.frames.new(1)
    
    gp_mat = bpy.data.materials.new(GREASE_PENCIL_MAT)
    bpy.data.materials.create_gpencil_data(gp_mat)
    gp.materials.append(gp_mat)

    obj = bpy.data.objects.new(name, gp)
    scene.collection.objects.link(obj)
    return obj

def create_lineart(source: 'Drawing_subject', style: str, 
        scene: bpy.types.Scene) -> bpy.types.Object:
    """ Create source.grease_pencil if needed and add a lineart modifier 
        with style to it """
    if style == 'c':
        source.obj.hide_viewport = True 
        cutter = source.drawing_context.cutter
        return cutter.lineart_gp
    elif style == 'b':
        camera = source.drawing_context.drawing_camera
        camera.reverse_cam()

    if not scene:
        scene = bpy.context.scene
    if not source.grease_pencil:
        source.set_grease_pencil(create_grease_pencil(
                GREASE_PENCIL_PREFIX + source.obj.name, scene))
    add_line_art_mod(source.grease_pencil, source.obj, 
            source.lineart_source_type, style)
    return source.grease_pencil

def join_coords(coords: list[tuple[float]]) -> list[list[tuple[float]]]:
    """ Join coords list (as from polyline) and put new coords lists in seqs """
    seqs = []
    for coord in coords:
        seqs = add_tail(seqs, coord)
    return seqs

def add_tail(sequences: list[list[tuple[float]]], tail: list[tuple[float]]) -> \
        list[list[tuple[float]]]:
    """ Add tail to sequences and join it to every sequence 
        whith corresponding ends """
    to_del = []
    new_seq = tail
    last_joined = None
    seqs = [seq for seq in sequences for t in [0, -1]]
    for i, seq in enumerate(seqs):
        t = -(i%2) ## -> alternate 0 and -1
        ends = [seq[0], seq[-1]]
        if new_seq[t] not in ends or last_joined == seq:
            continue
        index = -ends.index(new_seq[t]) ## -> 0 | 1
        step = (-2 * index) - 1 ## -> -1 | 1
        val = 1 if t == 0 else -1 ## -> 1 | -1 | 1 | -1
        ## Cut first or last and reverse f necessary
        seq_to_check = new_seq[1+t:len(new_seq)+t][::step*val]
        ## Compose accordingly
        new_seq = [ii for i in [seq,seq_to_check][::step] for ii in i]
        last_joined = seq
        if seq not in to_del:
            to_del.append(seq)
    for s in to_del:
        sequences.remove(s)
    sequences.append(new_seq)
    return sequences

def get_path_coords(coords: list[tuple[float]]) -> str:
    """ Return the coords as string for paths """
    closed = coords[0] == coords[-1]
    string_coords = 'M '
    for co in coords[:-1]:
        string_coords += f'{str(co[0])},{str(co[1])} '
    closing = 'Z ' if closed else f'{str(coords[-1][0])},{str(coords[-1][1])} '
    string_coords += closing
    return string_coords

def transform_points(points:list[tuple[float]], factor: float = 1, 
        rounding: int = 16) -> list[tuple[float]]:
    """ Scale and round points """ 
    new_points = []
    for coords in points:
        new_coord = tuple([round(co*factor, rounding) for co in coords])
        new_points.append(new_coord)
    return new_points

def make_active(obj: bpy.types.Object) -> None:
    """ Deselect all and make obj active """
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

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

