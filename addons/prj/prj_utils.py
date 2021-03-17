#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy, bmesh
from mathutils import Matrix
from mathutils import Vector
from mathutils import geometry
from bpy_extras.object_utils import world_to_camera_view

point_from_camera = lambda v, cam: world_to_camera_view(bpy.context.scene, cam, v)

def create_line_art_onto(source, source_type: str, occl_start: int = 0, 
        occl_end: int = 0) -> bpy.types.Object:
    """ Create a line art gp from source of the source_type """
    GREASE_PENCIL_MOD = 'prj_la'
    GREASE_PENCIL_MAT = 'prj_mat'
    GREASE_PENCIL_PREFIX = 'prj_'
    GREASE_PENCIL_LAYER = 'prj_lay'

    ## Create the grease pencil, its layer, material and frame and link to scene
    gp_name = GREASE_PENCIL_PREFIX + source.name
    gp = bpy.data.grease_pencils.new(gp_name)

    gp_layer = gp.layers.new(GREASE_PENCIL_LAYER)
    gp_layer.frames.new(1)
    
    gp_mat = bpy.data.materials.new(GREASE_PENCIL_MAT)
    bpy.data.materials.create_gpencil_data(gp_mat)
    gp.materials.append(gp_mat)

    obj = bpy.data.objects.new(gp_name, gp)
    bpy.context.collection.objects.link(obj)

    ## Create and setup lineart modifier
    obj.grease_pencil_modifiers.new(GREASE_PENCIL_MOD, 'GP_LINEART')
    gp_mod = obj.grease_pencil_modifiers[GREASE_PENCIL_MOD]
    gp_mod.target_layer = gp_layer.info
    gp_mod.target_material = gp_mat
    gp_mod.chaining_geometry_threshold = 0
    gp_mod.chaining_image_threshold = 0
    gp_mod.use_multiple_levels = True
    gp_mod.level_start = occl_start
    gp_mod.level_end = occl_end
    gp_mod.source_type = source_type
    if source_type == 'OBJECT':
        gp_mod.source_object = source
    elif source_type == 'COLLECTION':
        gp_mod.source_collection = source

    return obj

def mesh_by_verts(obj_name: str, verts: list[Vector]) -> bpy.types.Object:
    """ Create a mesh object from verts """
    mesh = bpy.data.meshes.new(obj_name)
    obj = bpy.data.objects.new(obj_name, mesh)
    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bm.from_object(obj, bpy.context.view_layer.depsgraph)
    for v in verts:
        bm.verts.new(v)

    bmesh.ops.contextual_create(bm, geom=bm.verts)
    bm.to_mesh(mesh)
    bm.free()

    return obj

def make_active(obj: bpy.types.Object) -> None:
    """ Deselect all and make obj active """
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def __point_in_quad(point: Vector, quad_vert: list[Vector]) -> bool:
    """ Check if point is inside quad (2d only) """
    intersect_point = geometry.intersect_point_quad_2d(point,
            quad_vert[0], quad_vert[1], quad_vert[2], quad_vert[3])
    if not intersect_point:
        return False
    return True

def __lines_intersect(a_0: Vector, a_1: Vector, b_0: Vector, b_1: Vector) -> bool:
    """ Check if lines a and b intersects (2d only) """
    intersect_point = geometry.intersect_line_line_2d(a_0, a_1, b_0, b_1)
    if not intersect_point:
        return False
    return True

def in_frame(cam: bpy.types.Object, 
        obj: bpy.types.Object) -> dict[str, bool]:
    """ Get visibility relation between cam and obj """

    BOUNDING_BOX_EDGES = ((0, 1), (0, 3), (0, 4), (1, 2), (1, 5), (2, 3), 
                        (2, 6), (3, 7), (4, 5), (4, 7), (5, 6), (6, 7))
    BOUNDING_BOX_FACES = ((0, 1, 2, 3), (2, 3, 7, 6), (6, 7, 4, 5),
                       (4, 5, 1, 0), (0, 4, 7, 3), (1, 5, 6, 2)) 
    FRAME_EDGES = (Vector((0,0)), Vector((1,0)), Vector((1,1)), Vector((0,1)))

    box = [(obj.matrix_world @ Vector(v)) for v in obj.bound_box]
    #print('ref_offset', ref_offset)
    #print('box', box)

    frontal = False
    behind = False
    framed = False
    
    bound_box_verts_from_cam = []
    ## If a vertex of bounding box is in camera_view then object is in
    for v in box:
        x, y, z = point_from_camera(v, cam)
        bound_box_verts_from_cam.append((x, y, z))

        if z >= cam.data.clip_start or z == 0.0:
            frontal = True
        else:
            behind = True
        if 1 >= x >= 0 and 1 >= y >= 0:
            #print(obj.name, "is FRAMED! (in vertex", v, ")")
            framed = True
    if framed:
        return {'framed': framed, 'frontal': frontal, 'behind': behind}
    else:
        ## Check if obect is bigger than frame
        for face in BOUNDING_BOX_FACES:
            face_verts = [bound_box_verts_from_cam[v] for v in face]
            if __point_in_quad(Vector((.5,.5,.0)), face_verts):
                framed = True
                return {'framed': framed, 'frontal': frontal, 'behind': behind}

        ## If an edge intersects camera frame then obj is in
        for e in BOUNDING_BOX_EDGES:
            box_edge = [Vector(point_from_camera(box[e[0]])[:2], cam),
                Vector(point_from_camera(box[e[1]])[:2], cam)]
            for i in range(4):
                if __lines_intersect(box_edge[0], box_edge[1], 
                        FRAME_EDGES[i], FRAME_EDGES[(i+1)%4]):
                    framed = True
                    return {'framed': framed, 'frontal': frontal, 'behind': behind}

    #print(obj.name, "is NOT FRAMED!")
    frontal = False
    behind = False
    return {'framed': framed, 'frontal': frontal, 'behind': behind}

def localize_obj(container: bpy.types.Object, 
        inner_obj: bpy.types.Object) -> bpy.types.Object:
    """ Make inner_obj located as if it was local based on container matrix """
    cnt_matrix = container.matrix_world.copy()
    cnt_instance_offset = container.instance_collection.instance_offset
    cnt_translated = cnt_matrix @ Matrix.Translation(-cnt_instance_offset)
    inner_obj.matrix_world = cnt_translated @ inner_obj.matrix_world
    return inner_obj

