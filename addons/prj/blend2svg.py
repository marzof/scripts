#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy
import os
import mathutils
from mathutils import Vector
from mathutils import Quaternion
import time
import svgutils

RENDER_ROTATION = .000001

def get_svg(cam, objs, collection, render_path):
    print('to blend2svg', cam, objs, collection, render_path)
    svgs = []
    for obj in objs:
        ## Rotate object to avoid rendering glitches
        actual_obj_rotation = obj.rotation_euler.copy()
        for i, angle in enumerate(obj.rotation_euler):
            obj.rotation_euler[i] = angle + RENDER_ROTATION
        ## Link object to rendering collection, 
        ## export svg and unlink it
        collection.objects.link(obj)
        fpath = render_path + os.sep + obj.name + '.svg'
        bpy.ops.wm.gpencil_export_svg(filepath=fpath,
            selected_object_type='VISIBLE')
        print(obj.name, 'exported')
        collection.objects.unlink(obj)
        ## Restore object previous rotation
        obj.rotation_euler = actual_obj_rotation
        svgs.append(fpath)
    return {'files': svgs,}
        
