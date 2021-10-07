#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy, bmesh
import os
import math
from PIL import Image
from mathutils import Matrix, Vector, geometry
from bpy_extras.object_utils import world_to_camera_view
from prj.drawing_style import drawing_styles
import time

BASE_ROUNDING: int = 6
MIN_UNIT_FRACTION = 2 ## 1 = 1 millimeter; 2 = 1/2 millimeter; 4 = 1/4 millimeter
f_to_8_bit = lambda c: int(hex(int(c * 255)),0)

def create_line_mesh_obj(name: str, vertices: list[Vector],
        collection: bpy.types.Collection) -> bpy.types.Object:
    """ Return a new mesh object using vertices """
    mesh = bpy.data.meshes.new(name)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    bm = bmesh.new()
    verts = [bm.verts.new(v) for v in vertices]
    edges = [bm.edges.new((verts[i], verts[i+1])) for i in range(len(verts)-1)]
    bm.to_mesh(mesh)
    bm.free()
    return obj

def add_modifier(obj: bpy.types.Object, mod_name: str, mod_type: str, 
        params: dict, gpencil: bool= False) -> bpy.types.Modifier:
    if gpencil:
        mod = obj.grease_pencil_modifiers.new(mod_name, mod_type)
    else:
        mod = obj.modifiers.new(mod_name, mod_type)
    for param in params:
        setattr(mod, param, params[param])
    return mod

def reverse_camera(camera: bpy.types.Camera) -> None:
    """ Inverse camera matrix for back views """
    camera.matrix_world = (get_translate_matrix(camera) @ camera.matrix_world) \
            @  Matrix().Scale(-1, 4, (.0,.0,1.0))

def get_translate_matrix(camera) -> Matrix:
    """ Get matrix for move camera towards his clip_start """
    normal_vector = Vector((0.0, 0.0, -2 * camera.data.clip_start))
    z_scale = round(camera.matrix_world.to_scale().z, BASE_ROUNDING)
    opposite_matrix = Matrix().Scale(z_scale, 4, (.0,.0,1.0))
    base_matrix = camera.matrix_world @ opposite_matrix
    translation = base_matrix.to_quaternion() @ (normal_vector * z_scale)
    return Matrix.Translation(translation)

def get_scene_tree(collection: bpy.types.Collection, scene_tree: dict = {},
        position: tuple[int] = (0,)) -> dict[tuple[int], bpy.types.Collection]:
    """ Populate scene_tree by scene collections and objects """
    scene_tree.update({position: collection})
    i = 0
    for child in collection.children:
        get_scene_tree(child, scene_tree, position + (i,))
        i += 1
    for j, obj in enumerate(collection.objects, start=i):
        scene_tree.update({position + (j,): obj})
    return scene_tree

def remove_grease_pencil(gpencil_obj: bpy.types.Object) -> None:
    for mod in gpencil_obj.grease_pencil_modifiers:
        ## Remove material from lineart to avoid error
        if mod.type == 'GP_LINEART':
            mod.target_material = None
    for material in gpencil_obj.data.materials:
        if not material:
            continue
        bpy.data.materials.remove(material)
    bpy.data.grease_pencils.remove(gpencil_obj.data)

def to_hex(c: float) -> str:
    """ Return srgb hexadecimal version of c """
    if c < 0.0031308:
        srgb = 0.0 if c < 0.0 else c * 12.92
    else:
        srgb = 1.055 * math.pow(c, 1.0 / 2.4) - 0.055
    return hex(max(min(int(srgb * 255 + 0.5), 255), 0))


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

class dotdict(dict):
    """dot.notation access to dictionary attributes"""
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__

def get_resolution(camera: bpy.types.Camera, scene: bpy.types.Scene, 
        drawing_scale: float = None) -> list[int]:
    """ Get scene render resolution based on drawing_scale """
    frame_size = camera.view_frame(scene=scene)
    scale_factor = drawing_scale * 1000 * MIN_UNIT_FRACTION
    x_size = int((frame_size[0].x - frame_size[2].x) * scale_factor)
    y_size = int((frame_size[0].y - frame_size[2].y) * scale_factor)
    return [x_size, y_size]

def get_render_data(objects: list[bpy.types.Object], 
        scene: bpy.types.Scene) -> 'Imaging_Core':
    """ Render the objects and get the pixels data """
    ### Move subjects to render_scene, render them and remove from scene
    for obj in objects:
        if obj not in list(scene.collection.objects):
            scene.collection.objects.link(obj)
    bpy.ops.render.render(write_still=True, scene=scene.name)
    for obj in objects:
        if obj in list(scene.collection.all_objects):
            scene.collection.objects.unlink(obj)

    ### Get the rendering data
    render = Image.open(scene.render.filepath)
    render_pixels = render.getdata()
    os.remove(scene.render.filepath)
    return render_pixels

def flatten(li: list) -> list:
    """ Flatten list li from its sublists """
    return [item for sublist in li for item in sublist]

def get_obj_bbox_by_cam(obj: bpy.types.Object, 
        camera: bpy.types.Object, matrix: Matrix = None) -> list[Vector]:
    """ Get object bounding box relative to camera frame"""
    if not matrix:
        matrix = obj.matrix_world
    world_obj_bbox = [matrix @ Vector(v) for v in obj.bound_box]
    bbox_from_cam_view = [world_to_camera_view(bpy.context.scene, 
        camera, v) for v in world_obj_bbox]
    return bbox_from_cam_view

def is_framed(object_instance: bpy.types.DepsgraphObjectInstance, 
        camera: bpy.types.Object) -> dict:
    """ Check if object_instance is viewed by camera, if is in front or 
        behind camera frame. If not inside_frame then object bounding box 
        is surrounding camera frame. It returns a dict with result and
        bounding box relative to camera frame """
    inst_obj = object_instance.object
    in_front = False
    behind = False

    ## TODO handle better (ok for some curves: e.g. the extruded ones, 
    ##      not custom shapes)
    if inst_obj.type not in ['CURVE', 'MESH']:
        return {'result': None, 'inside_frame': None, 'in_front': in_front, 
                'behind': behind, 'bound_box': None}

    matrix = inst_obj.matrix_world.copy()
    bound_box = get_obj_bbox_by_cam(inst_obj, camera, matrix)

    ## Check if object is in_front of and/or behind camera
    zs = [v.z for v in bound_box]
    z_min, z_max = min(zs), max(zs)
    cut_plane = camera.data.clip_start
    if cut_plane <= z_max: 
        in_front = True
    if z_min <= cut_plane: 
        behind = True

    ## Get instance inside camera frame
    for v in bound_box:
        if 0 <= v.x <= 1 and 0 <= v.y <= 1:
            return {'result': True, 'inside_frame': True, 'in_front': in_front, 
                    'behind': behind, 'bound_box': bound_box}

    ## Check if camera frame is in bound_box 
    ## (e.g. inst_obj surrounding cam frame)
    bound_box_min = bound_box[0]
    bound_box_max = bound_box[-1]
    for frame_x in [0, 1]:
        for frame_y in [0, 1]:
            frame_x_is_in = bound_box_min.x <= frame_x <= bound_box_max.x
            frame_y_is_in = bound_box_min.y <= frame_y <= bound_box_max.y
            if not frame_x_is_in or not frame_y_is_in:
                continue
            return {'result': True, 'inside_frame': False, 'in_front': in_front,
                    'behind': behind, 'bound_box': bound_box}

    ## Check if bound_box intersect camera frame
    bound_box_edge_idxs = [(0,1),(0,3),(0,4), (1,2), (1,5), (2,3), (2,6),
            (3,7), (4,5), (4,7), (5,6), (6,7)]
    checked_edges = []
    for edge in bound_box_edge_idxs:
        edge_p1 = Vector((bound_box[edge[0]].x, bound_box[edge[0]].y))
        edge_p2 = Vector((bound_box[edge[1]].x, bound_box[edge[1]].y))
        if edge_p1 - edge_p2 == 0:
            continue
        if (edge_p1, edge_p2) in checked_edges:
            continue
        if (edge_p2, edge_p1) in checked_edges:
            continue
        checked_edges.append((edge_p1, edge_p2))
        p1 = [(0,0), (1,1)]
        p2 = [(0,1), (1,0)]
        points = [(p1s, p2s) for p1s in p1 for p2s in p2]
        # [((0,0),(0,1)), ((0,0),(1,0)), ((1,1),(0,1)), ((1,1),(1,0))]
        for side in points:
            side_p1 = Vector(side[0])
            side_p2 = Vector(side[1])
            intersection = geometry.intersect_line_line_2d(edge_p1, edge_p2, 
                    side_p1, side_p2)
            if intersection:
                return {'result': True, 'inside_frame': False, 
                        'in_front': in_front, 'behind': behind, 
                        'bound_box': bound_box}
    return {'result': False, 'inside_frame': None,
            'in_front': in_front, 'behind': behind, 'bound_box': bound_box}

def is_cut(obj: bpy.types.Object, matrix: 'mathutils.Matrix', 
        cut_verts: list[Vector], cut_normal: Vector) -> bool:
    """ Check if an edge of (a mesh) obj intersect cut_verts quad plane """
    print('Get cut for', obj.name)
    mesh = obj.data
    for edge in mesh.edges:
        verts = edge.vertices
        v0 = matrix @ mesh.vertices[verts[0]].co
        v1 = matrix @ mesh.vertices[verts[1]].co
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
        if not point_on_cut_plane: ## intersection is out of quad cut plane
            continue
        #print('It cuts at', intersection)
        return True
    return False

def point_in_quad(point: Vector, quad_vert: list[Vector]) -> bool:
    """ Check if point is inside quad (2d only) """
    intersect_point = geometry.intersect_point_quad_2d(point,
            quad_vert[0], quad_vert[1], quad_vert[2], quad_vert[3])
    if not intersect_point:
        return False
    return True

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

