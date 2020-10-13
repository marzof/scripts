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

# TODO Dependencies: 
# - ODAFileConverter
# - Inkscape
# - pstoedit

import bpy
import os, sys
import re, random
import subprocess, shlex
from shutil import copyfile

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
BLANK_CAD = './blank.dwg'
ODA_FILE_CONVERTER = '/usr/bin/ODAFileConverter'
#CONTINUOUS_LINE_RE = r'AcDbLine\n(\s*62\n\s*0\n\s*6\n\s*CONTINUOUS\n)'
LINEWEIGHT_RE = r'\n\s*100\n\s*AcDbLine\n'
FACTOR_MARKER = '-f'
SCRIPT_NAME = 'script.scr'
FRAME = "{:04d}".format(bpy.context.scene.frame_current)
RENDER_FACTOR = 2 ## Multiply this value by 1000 to get render resolution
LARGE_RENDER_FACTOR = int(ARGS[ARGS.index(FACTOR_MARKER) + 1]) \
        if FACTOR_MARKER in ARGS else 1
BASE_ORTHO_SCALE = RENDER_FACTOR * LARGE_RENDER_FACTOR * 254.0/96.0
FREESTYLE_SETS = {
        'prj': { 'visibility': 'VISIBLE', 'silhouette': True, 'border': False,
            'contour': True, 'crease': True },
        'cut': { 'visibility': 'VISIBLE', 'silhouette': False, 'border': True,
            'contour': False, 'crease': False },
        'hid': { 'visibility': 'HIDDEN', 'silhouette': True, 'border': True,
            'contour': True, 'crease': True }
        }

undotted = lambda x: x.replace('.', '_')
void_svg = lambda x: False if '<path' in x else True

def create_tmp_collection():
    """ Create a tmp collection and link it to the actual scene """
    ## Set a random name for the render collection
    hash_code = random.getrandbits(32)
    collection_name = '%x' % hash_code
    while collection_name in [coll.name for coll in bpy.data.collections]:
        hash_code = random.getrandbits(32)
        collection_name = '%x' % hash_code

    render_collection = bpy.data.collections.new(collection_name)
    bpy.context.scene.collection.children.link(render_collection)
    print('Created tmp collection', collection_name) 
    print(render_collection) 
    return collection_name

def set_freestyle(tmp_name):
    ''' Enable Freestyle and set lineset and style for rendering '''
    bpy.context.scene.render.use_freestyle = True
    bpy.context.scene.svg_export.use_svg_export = True
    fs_settings = bpy.context.window.view_layer.freestyle_settings
    for ls in fs_settings.linesets:
        ls.show_render = False

    ## Create dedicated linesets
    linesets = {}
    for ls in FREESTYLE_SETS:
        linesets[ls] = fs_settings.linesets.new(tmp_name + '_' + ls)
        linesets[ls].show_render = False
        linesets[ls].select_by_collection = True
        linesets[ls].collection = bpy.data.collections[tmp_name]
        linesets[ls].visibility = FREESTYLE_SETS[ls]['visibility']
        linesets[ls].select_silhouette = FREESTYLE_SETS[ls]['silhouette']
        linesets[ls].select_border = FREESTYLE_SETS[ls]['border']
        linesets[ls].select_contour = FREESTYLE_SETS[ls]['contour']
        linesets[ls].select_crease = FREESTYLE_SETS[ls]['crease']

    return linesets

def get_objects(cam):
    """ Filter objects to collect """
    ## TODO set to just rendered objects
    objs = []
    for obj in bpy.context.selectable_objects:
        if obj.type not in ['MESH', 'CURVE']:
            continue
        objs.append(obj)
    return objs

def render_cam(cam, folder_path, objects, tmp_name, fs_linesets):
    ''' Execute render for every object and save them as svg '''

    ## 100% if cam ortho scale == base ortho scale
    render_scale = round(100 * cam.data.ortho_scale/BASE_ORTHO_SCALE)
    bpy.context.scene.render.resolution_percentage = render_scale

    for obj in objects:
        bpy.data.collections[tmp_name].objects.link(obj)
        bpy.context.scene.camera = cam

        for ls in fs_linesets:
            render_name = folder_path  + '/' + undotted(obj.name) + '_' + ls
            print('Render name:', render_name)
            fs_linesets[ls].show_render = True
            bpy.context.scene.render.filepath = render_name
            bpy.ops.render.render()
            fs_linesets[ls].show_render = False

            ## Rename svg to remove frame counting
            os.rename(render_name + FRAME + '.svg', render_name + '.svg')
        
        bpy.data.collections[tmp_name].objects.unlink(obj)


def svg2dwg(folder_path, drawing):
    ''' Convert svg to dxf '''
    render_path = folder_path + '/' + undotted(drawing)
    svg = render_path + '.svg'
    eps = render_path + '.eps'
    dxf = render_path + '.dxf'

    ## Remove svg not containing '<path'
    f_svg = open(svg, 'r')
    svg_content = f_svg.read()
    f_svg.close()
    if void_svg(svg_content):
        os.remove(svg)
    else:
        ## Run with Inkscape 0.92
        subprocess.run(['inkscape', '-f', svg, '-C', '-E', eps])
        os.remove(svg)

        ## Run with Inkscape 1.0
        ## subprocess.run(['inkscape', svg, '-C', '-o', eps])

        eps2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(
                str(LARGE_RENDER_FACTOR), str(LARGE_RENDER_FACTOR)) + \
                        "'dxf_s:-polyaslines -dumplayernames -mm' {} {}".format(eps, dxf)
        subprocess.run(eps2dxf, shell=True) 
        os.remove(eps)

        ## Change continuous lines and lineweight to ByBlock in dxfs
        f_dxf = open(dxf, 'r')
        dxf_content = f_dxf.read()
        f_dxf.close()

        dxf_linetype = re.sub(r'CONTINUOUS', r'ByBlock', dxf_content)
        dxf_lineweight = re.sub(LINEWEIGHT_RE, 
                r'\n370\n    -2\n100\nAcDbLine\n', dxf_linetype)

        f_dxf = open(dxf, 'w')
        f_dxf.write(dxf_lineweight)
        f_dxf.close()


        subprocess.run([ODA_FILE_CONVERTER, folder_path, folder_path, 'ACAD2010', 
            'DWG', '0', '1', undotted(drawing) + '.dxf'])
        os.remove(dxf)
        if drawing:
            return undotted(drawing)

def create_cad_script(dwgs, files_list, folder_path):
    ''' Create script to run on cad file '''
    print(dwgs)
    print(files_list)
    new_objs = list(set(dwgs) - set(files_list))
    del_objs = list(set(files_list) - set(dwgs))
    print('new', new_objs)
    print('new', bool(new_objs))
    print('del', del_objs)
    with open(folder_path + '/' + SCRIPT_NAME, 'w') as scr:
        if new_objs:
            for new_obj in new_objs:
                scr.write('XREF\na\n{}\n0,0,0\n1\n1\n0\n'.format(
                    folder_path + '/' + new_obj + '.dwg'))
        if del_objs:
            scr.write('XREF\nd\n{}'.format(','.join(del_objs)))
            for f in [folder_path + '/' + del_obj + '.dwg' 
                    for del_obj in del_objs]:
                os.remove(f)
    scr.close()

def get_render_args():
    ''' Get cameras and object based on args or selection '''
    selection = bpy.context.selected_objects
    render_args = []
    cams = []
    objs = []
    marker_index = -1
    for i, arg in enumerate(ARGS):
        if arg == FACTOR_MARKER:
            marker_index = i + 1
        elif i == marker_index:
            continue
        else:
            render_args.append(arg)

    for arg in render_args:
        try:
            item = bpy.data.objects[arg]
            if item.type == "CAMERA":
                cams.append(item)
            elif item.type == "MESH":
                objs.append(item)
        except:
            print(arg, 'not present')
            continue

    if not cams:
        cams = [obj for obj in selection if obj.type == 'CAMERA']
    if not objs:
        objs = [obj for obj in selection if obj.type in ['MESH', 'CURVE']]
    return {'cams': cams, 'objs': objs}

def prepare_files(path, folder_path, cam_name):
    ''' Prepare files and folder to receive new renders '''
    files_list = []
    if cam_name not in os.listdir(path):
        print('Create', folder_path)
        os.mkdir(folder_path)
    else:
        ## Folder already exists. Get the dwg inside it
        files_list = [os.path.splitext(ob)[0] for ob in os.listdir(folder_path) 
                if os.path.splitext(ob)[1] == '.dwg' ]
        print(folder_path, 'exists and contains:\n', files_list)

    ## If dwg doesn't exist, copy it from blank template
    if cam_name + '.dwg' not in os.listdir(path):
        print('Create', cam_name + '.dwg')
        copyfile(BLANK_CAD, cam_name + '.dwg')
    else: print(cam_name + '.dwg exists')

    return files_list

def main():
    path = bpy.context.scene.render.filepath
    #active = bpy.context.view_layer.objects.active

    bpy.context.scene.render.resolution_x = RENDER_FACTOR * 1000
    bpy.context.scene.render.resolution_y = RENDER_FACTOR * 1000

    cams = get_render_args()['cams']
    objs = get_render_args()['objs']

    tmp_name = create_tmp_collection()
    fs_linesets = set_freestyle(tmp_name)
    ## TODO set freestyle for back view

    for cam in cams:
        cam_name = undotted(cam.name)
        folder_path = path + cam_name
        objects = get_objects(cam) if not objs else objs
        print('Objects to render are:\n', [undotted(ob.name) for ob in objects])

        files_list = prepare_files(path, folder_path, cam_name)

        render_cam(cam, folder_path, objects, tmp_name, fs_linesets)

        dwg_raw_list = []
        drawings = [os.path.splitext(ob)[0] for ob in os.listdir(folder_path) 
                if os.path.splitext(ob)[1] == '.svg' ]
        for drawing in drawings:
            dwg_raw_list.append(svg2dwg(folder_path, drawing))

        dwgs = [d for d in dwg_raw_list if d]

        create_cad_script(dwgs, files_list, folder_path)

main()
