#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy

GREASE_PENCIL_MOD = 'prj_la'
GREASE_PENCIL_MAT = 'prj_mat'
GREASE_PENCIL_PREFIX = 'prj_'
GREASE_PENCIL_LAYER = 'prj_lay'

def create_line_art_onto(source, source_type, 
        occl_level_start = 0, occl_level_end = 0):
    """ Create a line art gp from source of the source_type """
    gp_name = GREASE_PENCIL_PREFIX + source.name

    gp_mat = bpy.data.materials.new(GREASE_PENCIL_MAT)
    bpy.data.materials.create_gpencil_data(gp_mat)

    gp = bpy.data.grease_pencils.new(gp_name)
    gp.materials.append(gp_mat)
    gp_layer = gp.layers.new(GREASE_PENCIL_LAYER)

    gp_layer.frames.new(1)

    obj = bpy.data.objects.new(gp_name, gp)
    obj.grease_pencil_modifiers.new(GREASE_PENCIL_MOD, 'GP_LINEART')
    gp_mod = obj.grease_pencil_modifiers[GREASE_PENCIL_MOD]
    gp_mod.target_layer = gp_layer.info
    gp_mod.target_material = gp_mat
    gp_mod.chaining_geometry_threshold = 0
    gp_mod.chaining_image_threshold = 0
    gp_mod.use_multiple_levels = True
    gp_mod.level_start = occl_level_start
    gp_mod.level_end = occl_level_end
    gp_mod.source_type = source_type
    if source_type == 'OBJECT':
        gp_mod.source_object = source
    elif source_type == 'COLLECTION':
        gp_mod.source_collection = source
    bpy.context.collection.objects.link(obj)

    return obj

def make_active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def in_frame(cam, obj, container):
    ''' Filter objs and return just those viewed from cam '''
    #print('Check visibility for', obj.name)
    linked = False
    if container.instance_collection:
        for inner_obj in container.instance_collection.all_objects:
            if obj == inner_obj:
                linked = True
                break
    if linked:
        print(obj.name, 'is linked')
        matrix = container.matrix_world
        #print('matrix', matrix)
        #print('obj matrix', obj.matrix_world)
        ref_offset = container.instance_collection.instance_offset
    else:
        matrix = Matrix((
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 0.0),
            (0.0, 0.0, 0.0, 1.0)))
        ref_offset = Vector((0.0, 0.0, 0.0))
    box = [matrix @ ((obj.matrix_world @ Vector(v)) - ref_offset) 
            for v in obj.bound_box]
    #print('ref_offset', ref_offset)
    #print('box', box)

    frontal = False
    behind = False
    framed = False

    bound_box_verts_from_cam = []
    ## If a vertex of bounding box is in camera_view then object is in
    for v in box:
        x, y, z = world_to_camera_view(bpy.context.scene, cam, v)
        bound_box_verts_from_cam.append((x, y, z))
        if z >= cam.data.clip_start:
            frontal = True
        else:
            behind = True
        if 1 >= x >= 0 and 1 >= y >= 0:
            #print(obj.name, "is FRAMED! (in vertex", v, ")")
            framed = True

    if not framed:
        ## Check if obect is bigger than frame
        for face in BOUNDING_BOX_FACES:
            face_verts = [bound_box_verts_from_cam[v] for v in face]
            intersect = geometry.intersect_point_quad_2d(
                    Vector((0.5, 0.5, 0.0)), 
                    face_verts[0], face_verts[1], face_verts[2], face_verts[3])
            if intersect:
                framed = True
                break

    if framed:
        return {'framed': framed, 'frontal': frontal, 'behind': behind}

    ## If an edge intersects camera frame then obj is in
    for e in BOUNDING_BOX_EDGES:
        box_edge = [Vector(world_to_camera_view(bpy.context.scene, cam, box[e[0]])[:2]),
            Vector(world_to_camera_view(bpy.context.scene, cam, box[e[1]])[:2])]
        for i in range(4):
            intersect = geometry.intersect_line_line_2d(
                box_edge[0], box_edge[1], FRAME_EDGES[i], FRAME_EDGES[(i+1)%4])
            #print('intersect in', intersect)
            if intersect:
                #print(obj.name, "is FRAMED! (intersects in", intersect, ")")
                framed = True
                return {'framed': framed, 'frontal': frontal, 'behind': behind}

    #print(obj.name, "is NOT FRAMED!")
    frontal = False
    behind = False
    return {'framed': framed, 'frontal': frontal, 'behind': behind}

def viewed_objects(cam, objs):
    """ Filter objects to collect """
    objects = []
    frontal_objs = []
    behind_objs = []
    referenced_objs = {}
    ## Use indicated objects (as args or selected) if any. Else use selectable
    objs = objs if len(objs) else bpy.context.selectable_objects 
    for obj in objs:
        if obj.type in RENDERABLES:
            if obj.type == 'EMPTY' and obj.instance_collection:
                referenced_objs[obj] = obj.instance_collection.all_objects
            elif obj.type != 'EMPTY':
                referenced_objs[obj] = [obj]
    for ref_obj in referenced_objs:
        for obj in referenced_objs[ref_obj]:
            framed = in_frame(cam, obj, ref_obj)
            if framed['framed'] and ref_obj not in objects:
                objects.append(ref_obj)
            if framed['frontal'] and ref_obj not in frontal_objs:
                frontal_objs.append(ref_obj)
            if framed['behind'] and ref_obj not in behind_objs:
                behind_objs.append(ref_obj)
            if ref_obj in objects and ref_obj in frontal_objs and \
                    ref_obj in behind_objs:
                        break
    return {'all': objects, 'frontal': frontal_objs, 'behind': behind_objs}
