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
from pathlib import Path

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
FLAGS = [arg for arg in ARGS if arg.startswith('-')]
BLANK_CAD = './blank.dwg'
ODA_FILE_CONVERTER = '/usr/bin/ODAFileConverter'
#CONTINUOUS_LINE_RE = r'AcDbLine\n(\s*62\n\s*0\n\s*6\n\s*CONTINUOUS\n)'
LINEWEIGHT_RE = r'\n\s*100\n\s*AcDbLine\n'
FACTOR_MARKER = '-f'
LINESTYLE_MARKER = {
        'p': 'prj',
        'h': 'hid',
        'c': 'cut',
        'b': 'bak'
        }
SCRIPT_NAME = 'script.scr'
FRAME = "{:04d}".format(bpy.context.scene.frame_current)
RENDER_FACTOR = 2 ## Multiply this value by 1000 to get render resolution
LARGE_RENDER_FACTOR = int(ARGS[ARGS.index(FACTOR_MARKER) + 1]) \
        if FACTOR_MARKER in ARGS else 1
RENDERABLE_ARGS = list(set(ARGS) - set(FLAGS) - 
        set([str(LARGE_RENDER_FACTOR) * (FACTOR_MARKER in ARGS)]))
BASE_ORTHO_SCALE = RENDER_FACTOR * LARGE_RENDER_FACTOR * 254.0/96.0
RENDERABLES = ['MESH', 'CURVE', 'EMPTY']
FREESTYLE_SETS = {
        'prj': { 'visibility': 'VISIBLE', 'silhouette': True, 'border': False,
            'contour': True, 'crease': True },
        'cut': { 'visibility': 'VISIBLE', 'silhouette': False, 'border': True,
            'contour': False, 'crease': False },
        'hid': { 'visibility': 'HIDDEN', 'silhouette': True, 'border': True,
            'contour': True, 'crease': True },
        'bak': { 'visibility': 'VISIBLE', 'silhouette': True, 'border': False,
            'contour': True, 'crease': True },
        }
RENDERABLE_STYLES = [LINESTYLE_MARKER[lm] for lm in LINESTYLE_MARKER 
        if lm in list(''.join(FLAGS))]

undotted = lambda x: x.replace('.', '_')
void_svg = lambda x: False if '<path' in x else True

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
    print('Created tmp collection', collection_name) 
    print(render_collection) 
    return collection_name

def set_freestyle(tmp_name):
    ''' Enable Freestyle and set lineset and style for rendering '''
    bpy.context.scene.render.use_freestyle = True
    bpy.context.scene.svg_export.use_svg_export = True
    fs_settings = bpy.context.window.view_layer.freestyle_settings
    ## Disable existing linesets
    for ls in fs_settings.linesets:
        ls.show_render = False

    ## Create dedicated linesets
    linesets = {}
    for ls in [fs for fs in FREESTYLE_SETS if fs in RENDERABLE_STYLES]:
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
    ## TODO set to just viewed objects
    ## TODO cut render only for actual cut objects
    ## TODO bak render only for actual rear objects

    objs = []
    for obj in bpy.context.selectable_objects:
        if obj.type in RENDERABLES:
            objs.append(obj)
    return objs

def set_back(cam):
    ''' Invert cam direction to render back view '''

    bpy.ops.object.select_all(action='DESELECT')
    cam.select_set(True)
    bpy.context.view_layer.objects.active = cam

    bpy.ops.transform.resize(value=(1,1,-1), orient_type='LOCAL')
    bpy.ops.transform.translate(value=(0,0,2*cam.data.clip_start), 
            orient_type='LOCAL')

def render_cam(cam, folder_path, objects, tmp_name, fs_linesets):
    ''' Execute render for every object and save them as svg '''

    ## 100% if cam ortho scale == base ortho scale
    render_scale = round(100 * cam.data.ortho_scale/BASE_ORTHO_SCALE)
    bpy.context.scene.render.resolution_percentage = render_scale
    cam_name = undotted(cam.name)

    for obj in objects:
        bpy.data.collections[tmp_name].objects.link(obj)
        bpy.context.scene.camera = cam

        for ls in fs_linesets:
            render_name = folder_path  + '/' + ls + '/' + cam_name + '-' + \
                    undotted(obj.name) + '_' + ls
            print('Render name:', render_name)
            fs_linesets[ls].show_render = True
            bpy.context.scene.render.filepath = render_name
            if ls == 'bak':
                set_back(cam)
                bpy.ops.render.render()
                set_back(cam)
            else:
                bpy.ops.render.render()
            fs_linesets[ls].show_render = False

            ## Rename svg to remove frame counting
            os.rename(render_name + FRAME + '.svg', render_name + '.svg')
        
        bpy.data.collections[tmp_name].objects.unlink(obj)

def get_file_content(f):
    f = open(f, 'r')
    f_content = f.read()
    f.close()
    return f_content

def svg2dxf(folder_path, svg_file):
    ''' Convert svg to dxf '''
    render_path = os.path.splitext(svg_file)[0]
    svg = svg_file
    eps = render_path + '.eps'
    dxf = render_path + '.dxf'

    eps2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(
        str(LARGE_RENDER_FACTOR), str(LARGE_RENDER_FACTOR)) + \
            "'dxf_s:-polyaslines -dumplayernames -mm' {} {}".format(eps, dxf)

    ## Remove svg not containing '<path'
    svg_content = get_file_content(svg)
    if void_svg(svg_content):
        os.remove(svg)
    else:
        ## Run with Inkscape 0.92
        subprocess.run(['inkscape', '-f', svg, '-C', '-E', eps])
        os.remove(svg)

        ## Run with Inkscape 1.0
        ## subprocess.run(['inkscape', svg, '-C', '-o', eps])

        subprocess.run(eps2dxf, shell=True) 
        os.remove(eps)

        ## Change continuous lines and lineweight to ByBlock in dxfs
        dxf_content = get_file_content(dxf)

        dxf_linetype = re.sub(r'CONTINUOUS', r'ByBlock', dxf_content)
        dxf_lineweight = re.sub(LINEWEIGHT_RE, 
                r'\n370\n    -2\n100\nAcDbLine\n', dxf_linetype)

        f_dxf = open(dxf, 'w')
        f_dxf.write(dxf_lineweight)
        f_dxf.close()

        return dxf

def create_cad_script(dwgs, existing_files, folder_path, path):
    ''' Create script to run on cad file '''
    print('dwgs:', dwgs)
    print('existing files:', existing_files)
    new_objs = list(set(dwgs) - set(existing_files))
    print('new files:', new_objs)
    if new_objs:
        with open(folder_path + '/' + SCRIPT_NAME, 'w') as scr:
            ## Add new files only to script
            for new_obj in new_objs:
                rel_obj = new_obj[len(path):]
                scr.write('XREF\na\n{}\n0,0,0\n1\n1\n0\n'.format(rel_obj))
        scr.close()

def get_render_args():
    ''' Get cameras and object based on args or selection '''
    selection = bpy.context.selected_objects
    cams = []
    objs = []

    ## Check arguments first
    for arg in RENDERABLE_ARGS:
        try:
            item = bpy.data.objects[arg]
            if item.type == "CAMERA":
                cams.append(item)
            elif item.type in RENDERABLES:
                objs.append(item)
        except:
            print(arg, 'not present')
            continue

    ## Get selected cams or objs if no arguments are provided
    if not cams:
        cams = [obj for obj in selection if obj.type == 'CAMERA']
    if not objs:
        objs = [obj for obj in selection if obj.type in RENDERABLES]
    return {'cams': cams, 'objs': objs}

def prepare_files(listdir, folder_path, cam_name):
    ''' Prepare files and folder to receive new renders '''
    existing_files = []
    if cam_name not in listdir:
        print('Create', folder_path)
        os.mkdir(folder_path)
        for fs in FREESTYLE_SETS:
            os.mkdir(folder_path + '/' + fs)
    else:
        ## Folder already exists. Get the dwgs inside it
        existing_files = [str(fi) for fi in list(Path(folder_path).rglob('*.dwg'))]
        print(folder_path, 'exists and contains:\n', existing_files)

    ## If dwg doesn't exist, copy it from blank template
    if cam_name + '.dwg' not in listdir:
        print('Create', folder_path + '.dwg')
        copyfile(BLANK_CAD, folder_path + '.dwg')
    else: 
        print(cam_name + '.dwg exists')

    return existing_files

def main():
    path = bpy.context.scene.render.filepath

    bpy.context.scene.render.resolution_x = RENDER_FACTOR * 1000
    bpy.context.scene.render.resolution_y = RENDER_FACTOR * 1000

    render_args = get_render_args()
    cams = render_args['cams']
    objs = render_args['objs']

    tmp_name = create_tmp_collection()
    fs_linesets = set_freestyle(tmp_name)

    for cam in cams:
        cam_name = undotted(cam.name)
        folder_path = path + cam_name
        objects = get_objects(cam) if not objs else objs
        print('Objects to render are:\n', [ob.name for ob in objects])

        existing_files = prepare_files(os.listdir(path), folder_path, cam_name)

        render_cam(cam, folder_path, objects, tmp_name, fs_linesets)

        svgs = [str(fi) for fi in list(Path(folder_path).rglob('*.svg'))]
        dxfs = list(filter(None, [svg2dxf(folder_path, svg_f) for svg_f in svgs]))

        subprocess.run([ODA_FILE_CONVERTER, folder_path, folder_path, 'ACAD2010', 
            'DWG', '1', '1', '*.dxf'])
        for d in dxfs:
            os.remove(d)

        dwgs = [re.sub('\.dxf$', '.dwg', dxf) for dxf in dxfs]
        create_cad_script(dwgs, existing_files, folder_path, path)

main()
