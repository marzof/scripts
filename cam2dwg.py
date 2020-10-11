#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

# Copyright (c) 2019 Marco Ferrara

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
# - ODAFileConverter
# - Inkscape
# - pstoedit


## TODO: make universal (no fixed layer names). Use just first 8 colors:
## C00-00-00-BLACK
## CFF-FF-FF-WHITE
## CFF-00-00 (red)
## CFF-FF-00 (yellow)
## ...
## bpy.data.linestyles["LineStyle.002"].color -> Color((1.0, 1.0, 0.0))

import sys
import bpy
import bmesh
import subprocess, shlex
import re


oda_file_converter = '/usr/bin/ODAFileConverter'
args = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
large_render_factor = 1

layers = {'cut': ['C00-FF-FF'],
        'proj': ['CFF-00-00'],
        'hid': ['C11-00-00'],
        'back': ['C00-00-FF'],
        '0': ['CFF-FF-FF-WHITE', 'C00-00-00-BLACK'],
        }

selection = bpy.context.selected_objects
active = bpy.context.view_layer.objects.active

factor_marker = '-f'
if factor_marker in args:
    factor_index = args.index(factor_marker) + 1 
    large_render_factor = int(args[factor_index])
    print('### Render factor:', large_render_factor)
    del args[factor_index - 1 : factor_index + 1]

if not args:
    cams = [obj for obj in selection if obj.type == 'CAMERA']
else:
    cams = [bpy.data.objects[arg] for arg in args]
frame = "{:04d}".format(bpy.context.scene.frame_current)
renders = []

path = bpy.context.scene.render.filepath

back_view = 'Back_view'
back_label = '_BACK'
freestyle_layers_label = 'Freestyle_layers'
#raw_label = '_RAW_'
raw_label = ''
factor = 2
bpy.context.scene.render.resolution_x = factor * 1000
bpy.context.scene.render.resolution_y = factor * 1000
base_ortho_scale = factor * large_render_factor * 254.0/96.0
freestyle_settings = bpy.context.window.view_layer.freestyle_settings
freestyle_linesets = {ls.name: ls.show_render for ls in freestyle_settings.linesets}

def set_back(cam, direction):
    bpy.ops.transform.resize(value=(1,1,-1), orient_type='LOCAL')
    bpy.ops.transform.translate(value=(0,0,2*cam.data.clip_start*direction), 
            orient_type='LOCAL')


def finalize_render(render_name):
    global renders
    subprocess.run('mv ' + render_name + frame + '.svg ' + render_name + '.svg',
            shell=True)

    renders.append(render_name)

def back_render(cam, render_filename):
    bpy.ops.object.select_all(action='DESELECT')
    cam.select_set(True)
    bpy.context.view_layer.objects.active = cam
    
    set_back(cam, -1)

    for ls in freestyle_settings.linesets:
        ls.show_render = False
        if ls.name == 'Back':
            ls.show_render = True

    bpy.context.scene.render.filepath = render_filename + back_label
    bpy.ops.render.render()

    ## Reset to start conditions (for non back view)
    set_back(cam, 1)
    for ls in freestyle_settings.linesets:
        ls.show_render = freestyle_linesets[ls.name]

    bpy.ops.object.select_all(action='DESELECT')
    for obj in selection:
       obj.select_set(True)
    bpy.context.view_layer.objects.active = active

    finalize_render(render_filename + back_label)

def render_cam(cam):
    render_scale = round(100 * cam.data.ortho_scale/base_ortho_scale)
    bpy.context.scene.render.resolution_percentage = render_scale

    render_filename = path + raw_label + cam.name 

    if freestyle_layers_label in cam.data.keys():
        freestyle_layers = [l.strip() for 
                l in cam.data[freestyle_layers_label].split(',')]

        ## Activate freestyle linesets
        for ls in freestyle_settings.linesets:
            ls.show_render = False
            if ls.name in freestyle_layers:
                ls.show_render = True


    bpy.context.scene.render.filepath = render_filename
    bpy.context.scene.camera = cam
    bpy.ops.render.render()

    finalize_render(render_filename)


    ## Render back view if needed
    if back_view in cam.data.keys() and cam.data[back_view]:
        back_render(cam, render_filename)

    ## Reset freestyle linesets
    for ls in freestyle_settings.linesets:
        ls.show_render = freestyle_linesets[ls.name]

def svg2dwg(render):
    svg = render + '.svg'
    eps = render + '.eps'
    dxf = render + '.dxf'

    ## Run with Inkscape 0.92
    subprocess.run(['inkscape', '-f', svg, '-C', '-E', eps])

    ## Run with Inkscape 1.0
    ## subprocess.run(['inkscape', svg, '-C', '-o', eps])

    svg2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(
            str(large_render_factor), str(large_render_factor)) + \
                    "'dxf_s:-polyaslines -ctl -mm' {} {}".format(eps, dxf)
    subprocess.run(svg2dxf, shell=True) 

    print('Get dxf content from', dxf)
    dxf_f = open(dxf, 'rt')
    dxf_data = dxf_f.read()
    for layer in layers:
        for lay in layers[layer]:
            print('Replace', lay, 'with', layer)
            dxf_data = dxf_data.replace(lay, layer)
    dxf_f.close()
    dxf_f = open(dxf, 'wt')
    print('Rewrite', dxf)
    dxf_f.write(dxf_data)
    dxf_f.close()

    subprocess.run([oda_file_converter, path, path, 'ACAD2013', 'DWG', 
        '0', '1', render[len(path):] + '.dxf'])
    subprocess.run(['rm', svg, eps, dxf])

def main():
    bpy.ops.object.select_all(action='DESELECT')
    bpy.ops.object.bevel_switcher(mode='allOFF')
    global renders

    for cam in cams:
        render_cam(cam)
        
        for render in renders:
            svg2dwg(render)

        ## Reset renders to []
        renders = []


main()


