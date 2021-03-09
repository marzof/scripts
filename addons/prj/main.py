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
from prj import svg

norm_path = lambda x: os.path.realpath(x).replace(
        os.path.realpath('.'), '').strip(os.sep)

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
#FLAGS = [arg for arg in ARGS if arg.startswith('-')]
FILE_PATH = bpy.path.abspath("//")
RENDER_PATH = norm_path(bpy.context.scene.render.filepath)
GREASE_PENCIL_MOD = 'prj_gp_la'
GREASE_PENCIL_MAT = 'prj_gp_mat'
CAM_SIZE_PLANE_SUFFIX = '_size_ref'
GREASE_PENCIL_PREFIX = 'prj_gp_'
GREASE_PENCIL_LAYER = 'prj_gp_lay'




def get_render_assets(args):
    """ Get render assets from args and convert it to dict """
    r_a = {}
    for arg in args:
        if isinstance(ast.literal_eval(arg), dict):
            dict_arg = ast.literal_eval(arg)
            for k in dict_arg:
                r_a[k] = [bpy.data.objects[name] for name in dict_arg[k]]
    return r_a

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
    mesh = bpy.data.meshes.new(cam.name + CAM_SIZE_PLANE_SUFFIX)
    obj = bpy.data.objects.new(cam.name + CAM_SIZE_PLANE_SUFFIX, mesh)

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

def create_line_art_onto(source, source_type):
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

render_assets = get_render_assets(ARGS)
tmp_collection = create_tmp_collection()

for cam in render_assets['cams']:
    bpy.context.scene.camera = cam
    size_plane_mesh = add_size_plane_mesh(cam)
    size_plane_gp = create_line_art_onto(size_plane_mesh, 'OBJECT')
    drawing_la_gp = create_line_art_onto(tmp_collection, 'COLLECTION')
    make_active(drawing_la_gp)
    svg_data = blend2svg.get_svg(cam, render_assets['objs'],
            tmp_collection, FILE_PATH + RENDER_PATH)
    print(svg_data)
#for svg_file in svg_data['files']:
#    svg.set_data(svg_data['frame_size'])
#    svg.read_svg(svg_file, svg_data['frame_name'], svg_data['line_art_name'])
