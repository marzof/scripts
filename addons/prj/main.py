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

print('\n\n\n###################################\n\n\n')

import bpy, bmesh
import sys, os
import ast, random
from prj import blend2svg
from prj import svg_lib
from mathutils import Vector
from mathutils import geometry
from mathutils import Matrix
#import svgutils
from bpy_extras.object_utils import world_to_camera_view



undotted = lambda x: x.replace('.', '_')

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
FLAGS = ARGS[0].replace('-', '') if ARGS else 'cp'
RENDER_PATH = bpy.path.abspath(bpy.context.scene.render.filepath)
GREASE_PENCIL_MOD = 'prj_la'
GREASE_PENCIL_MAT = 'prj_mat'
CAM_SIZE_PLANE = 'size_frame'
GREASE_PENCIL_PREFIX = 'prj_'
GREASE_PENCIL_LAYER = 'prj_lay'
RENDERABLES = ['MESH', 'CURVE', 'EMPTY']
SVG_GROUP_PREFIX = 'blender_object_' + GREASE_PENCIL_PREFIX
OCCLUSION_LEVELS = { 'cp': (0,0), 'h': (1,128), 'b': (0,128), }

def get_render_assets(args):
    """ Get render assets from args and convert it to dict """
    r_a = {}
    if isinstance(ast.literal_eval(args), dict):
        dict_arg = ast.literal_eval(args)
        for k in dict_arg:
            r_a[k] = [bpy.data.objects[name] for name in dict_arg[k]]
    return r_a

def get_render_assets_cl():
    ''' Get cameras and object based on selection if run by command line '''
    selection = bpy.context.selected_objects
    cams = [obj.name for obj in selection if obj.type == 'CAMERA']
    objs = [obj.name for obj in selection if obj.type in RENDERABLES]
    return {'cams': cams, 'objs': objs}

ASSETS = ARGS[1] if ARGS else str(get_render_assets_cl())

def create_tmp_collection():
    """ Create a tmp collection and link it to the actual scene """
    ## Set a random name for the render collection
    hash_code = random.getrandbits(32)
    collection_name = '%x' % hash_code
    ## If collection name exists get a new name
    while collection_name in [coll.name for coll in bpy.data.collections]:
        hash_code = random.getrandbits(32)
        collection_name = '%x' % hash_code

    ## Create the new collection and link it to the scene
    render_collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(render_collection)
    print('Created tmp collection', render_collection)
    return render_collection

def add_size_plane_mesh(cam):
    """ Create a plane at the clip end of cam with same size of cam frame """
    mesh = bpy.data.meshes.new(CAM_SIZE_PLANE)
    obj = bpy.data.objects.new(CAM_SIZE_PLANE, mesh)

    bpy.context.collection.objects.link(obj)

    bm = bmesh.new()
    bm.from_object(obj, bpy.context.view_layer.depsgraph)

    for v in cam.data.view_frame():
        bm.verts.new(v[:2] + (-(cam.data.clip_end - .01),))

    bmesh.ops.contextual_create(bm, geom=bm.verts)

    bm.to_mesh(mesh)
    bm.free()
    obj.matrix_world = cam.matrix_world
    return obj

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

## Start tracking process -> file class: receiving signals from steps
class Tracker:
    def start_tracking():
        pass
    def write_step():
        pass
    def stop_tracking():
        pass

## Check scene: naming, args, paths... -> class: verify naming conflict with files
class Draw_maker:
    def get_args():
        pass
    def get_file_paths():
        pass
## Prepare scene: collection, line art... -> class:
    def prepare_scene():
        pass
#    def draw_from_cam(class Cam):
#        pass

## for cam in cams:
##     Prepare files and folders if missing, get existing svg links...
## 
##     Prepare camera (size frame, back view)
## 
##     Check objects viewing condition: frontal, rear, cut...
##     Prepare objects: cut objetcs, linked object
##     
##     for obj in objs:
##         Prepare export (rotate obj, link to collection, rename line art)
##         Export svg
##         Reset for next export
##
##         Read svg
##         Rewrite svg (fix size and scale, closed polyline for cuts, import css)
##
##     Compose cam.svg
##     Reset scene (remove cuts) for next cam

## DATA STRUCTURE
## /assets
##     /components
##         /obj
##             /reprs
##                 obj_cam_type.svg
##                 obj_cam_type.svg
##                 obj_cam_type.svg
##                 obj_cam_type.svg
##             /other_things
##                 other_file
##                 other_file
##                 other_file
##             other_file
##             other_file
##             other_file
##         /obj
##             /reprs
##                 obj_cam_type.svg
##                 obj_cam_type.svg
##                 obj_cam_type.svg
##                 obj_cam_type.svg
##             /other_things
##                 other_file
##                 other_file
##                 other_file
##             other_file
##             other_file
##             other_file
##     /reprs
##         cam_0.svg
##         cam_1.svg
##         cam_1.css
##         cam_2.svg
##     /boards
##         cam_0.pdf
##         cam_1.pdf
##         cam_2.pdf
##     /other_things
##         other_file
##         other_file
##         other_file
##     /other_things
##         other_file
##         other_file
##         other_file
##     base.css
##     other_file
##     other_file
##     other_file
        

def main():
    render_assets = get_render_assets(ASSETS)
    tmp_collection = create_tmp_collection()
    objs = render_assets['objs']
    drawing_la_gp = create_line_art_onto(tmp_collection, 'COLLECTION',
            OCCLUSION_LEVELS[FLAGS][0], OCCLUSION_LEVELS[FLAGS][1])
    make_active(drawing_la_gp)
    for cam in render_assets['cams']:
        size_plane_mesh = add_size_plane_mesh(cam)
        size_plane_la_gp = create_line_art_onto(size_plane_mesh, 'OBJECT', 
                OCCLUSION_LEVELS['b'][0], OCCLUSION_LEVELS['b'][1])
        print('Viewed objects', viewed_objects(cam, objs))
        svg_files = blend2svg.get_svg(cam, objs, drawing_la_gp,
                tmp_collection, RENDER_PATH)
        print('svg files:', svg_files)
        for svg_f in svg_files:
            svg, drawing_g, frame_g = svg_lib.read_svg(svg_f['path'],
                    SVG_GROUP_PREFIX + svg_f['obj'],
                    SVG_GROUP_PREFIX + CAM_SIZE_PLANE) 
            svg_lib.write_svg(svg, drawing_g, frame_g, cam.data.ortho_scale, 
                    svg_f['path'])
main()
