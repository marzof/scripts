#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy, bmesh
from mathutils import Matrix, Vector, geometry
from bpy_extras.object_utils import world_to_camera_view

## TODO develop this
def clip_cut(prj_layer, cut_layer):
    #clipper = Clipper()
    prj_points, cut_points = [], []

    prj_entities = list(prj_layer.entities.values())[0][0].entities
    for entity in prj_entities:
        if entity == 'path':
            for path in prj_entities[entity]:
                prj_points.append(path.points)

    cut_entities = list(cut_layer.entities.values())[0][0].entities
    for entity in cut_entities:
        if entity == 'path':
            for path in cut_entities[entity]:
                cut_points.append(path.points)

    #new_prj_points = clipper.clip(cut_points, prj_points)

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

