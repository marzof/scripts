#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import bpy
import os
import mathutils
from mathutils import Vector
from mathutils import Quaternion
import svgutils

RENDER_ROTATION = .000001

def get_svg(cam, objs, la_gp, collection, render_path):
    initial_la_name = la_gp.name
    print(la_gp.name)
    print(collection.name)
    svgs = []
    for obj in objs:
        ## Rotate object to avoid rendering glitches
        actual_obj_rotation = obj.rotation_euler.copy()
        for i, angle in enumerate(obj.rotation_euler):
            obj.rotation_euler[i] = angle + RENDER_ROTATION
        ## Link object to rendering collection, 
        ## export svg and unlink it
        collection.objects.link(obj)
        fpath = render_path + obj.name + '.svg'
        ## Change la_gp name removing collection name
        la_gp.name = la_gp.name.replace(collection.name, obj.name)
        bpy.ops.wm.gpencil_export_svg(filepath=fpath,
            selected_object_type='VISIBLE')
        print(obj.name, 'exported')
        ## Reset la_gp name
        la_gp.name = initial_la_name
        collection.objects.unlink(obj)
        ## Restore object previous rotation
        obj.rotation_euler = actual_obj_rotation
        svgs.append({'path': fpath, 'obj': obj.name})
    return svgs
        
