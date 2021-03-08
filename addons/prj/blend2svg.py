#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy
import os
import mathutils
from mathutils import Vector
from mathutils import Quaternion
import time
import svgutils

obj_names = ['Cube', 'Sphere', 'Torus', 'Wall_cut']
objs = [bpy.data.objects[obj] for obj in obj_names]
frame_la = bpy.data.objects['frame_la']
lineart = bpy.data.objects['line_art']
camera = bpy.data.objects['Cam']
camera.rotation_mode = 'QUATERNION'
RENDER_ROTATION = .000001


#def set_view():
#    for area in bpy.context.screen.areas:
#        if area.type == "VIEW_3D":
#            for region in area.regions:
#                if region.type == "WINDOW":
#                    space = area.spaces[0]
#                    context_override = bpy.context.copy()
#                    context_override['area'] = area
#                    context_override['region'] = region
#                    context_override['space_data'] = space
#                    r3d = space.region_3d
#                    r3d.view_perspective = camera.data.type
#                    r3d.view_matrix = camera.matrix_world
#                    r3d.view_distance = camera.data.ortho_scale
#                    break
#            break
#    bpy.context.scene.camera = camera
#    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)


def make_active(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    

def get_svg(render_path):
    make_active(lineart)
    svgs = []
    for obj in objs:
        ## Rotate object to avoid rendering glitches
        actual_obj_rotation = obj.rotation_euler.copy()
        for i, angle in enumerate(obj.rotation_euler):
            obj.rotation_euler[i] = angle + RENDER_ROTATION
        ## Link object to rendering collection, 
        ## export svg and unlink it
        bpy.data.collections['render'].objects.link(obj)
        fpath = render_path + os.sep + obj.name + '.svg'
        bpy.ops.wm.gpencil_export_svg(filepath=fpath,
            selected_object_type='VISIBLE')
        print(obj.name, 'exported')
        bpy.data.collections['render'].objects.unlink(obj)
        ## Restore object previous rotation
        obj.rotation_euler = actual_obj_rotation
        svgs.append(fpath)
    return {'files': svgs, 'frame_size': camera.data.ortho_scale,
            'frame_name': frame_la.name, 'line_art_name': lineart.name}
        
