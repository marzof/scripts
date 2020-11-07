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

import bpy
import os, sys
import re, random
import subprocess, shlex
from shutil import copyfile
from pathlib import Path

check_list = lambda x, alt: x if x else alt
undotted = lambda x: x.replace('.', '_')
norm_path = lambda x: os.path.realpath(x).replace(
        os.path.realpath('.'), '').strip(os.sep)

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
FLAGS = [arg for arg in ARGS if arg.startswith('-')]
BLANK_CAD = './blank.dwg'
ODA_FILE_CONVERTER = '/usr/bin/ODAFileConverter'
#CONTINUOUS_LINE_RE = r'AcDbLine\n(\s*62\n\s*0\n\s*6\n\s*CONTINUOUS\n)'
LINEWEIGHT_RE = r'\n\s*100\n\s*AcDbLine\n'
LINESTYLE_LAYER_RE = r'.*(_.*)\.dwg'
FACTOR_MARKER = '-f'
SCRIPT_NAME = 'script.scr'
FRAME = "{:04d}".format(bpy.context.scene.frame_current)
RENDER_FACTOR = 2 ## Multiply this value by 1000 to get render resolution
LARGE_RENDER_FACTOR = int(ARGS[ARGS.index(FACTOR_MARKER) + 1]) \
        if FACTOR_MARKER in ARGS else 1
RENDERABLE_ARGS = list(set(ARGS) - set(FLAGS) - 
        set([str(LARGE_RENDER_FACTOR) * (FACTOR_MARKER in ARGS)]))
DISABLED_OBJS = {obj for obj in bpy.data.objects if obj.hide_render}
RESOLUTION_RATIO = 254.0/96.0
BASE_ORTHO_SCALE = RENDER_FACTOR * LARGE_RENDER_FACTOR * RESOLUTION_RATIO
RENDERABLES = ['MESH', 'CURVE', 'EMPTY']
FREESTYLE_SETS = {
        'prj': { 'flag': 'p', 'visibility': 'VISIBLE', 'silhouette': True, 
            'border': False, 'contour': True, 'crease': True },
        'cut': { 'flag': 'c', 'visibility': 'VISIBLE', 'silhouette': False, 
            'border': True, 'contour': False, 'crease': False },
        'hid': { 'flag': 'h', 'visibility': 'HIDDEN', 'silhouette': True, 
            'border': True, 'contour': True, 'crease': True },
        'bak': { 'flag': 'b', 'visibility': 'VISIBLE', 'silhouette': True, 
            'border': False, 'contour': True, 'crease': True },
        }
RENDERABLE_STYLES = check_list([ls for ls in FREESTYLE_SETS if 
    FREESTYLE_SETS[ls]['flag'] in list(''.join(FLAGS))], 
    [ls for ls in FREESTYLE_SETS])
RENDER_PATH = norm_path(bpy.context.scene.render.filepath)


print('\n\n\n###################################\n\n\n')


class Cam():
    def __init__(self, obj, name, folder_path, existing_files, objects):
        self.obj = obj
        self.name = name
        self.folder_path = folder_path
        self.script = self.folder_path + os.sep + SCRIPT_NAME
        self.existing_files = existing_files
        self.objects = objects
        self.svgs = []
        self.dxfs = []
        self.dwgs = []

    def set_resolution(self):
        ''' Set resolution for camera '''
        ## 100% if cam ortho scale == base ortho scale
        render_scale = round(100 * self.obj.data.ortho_scale/BASE_ORTHO_SCALE)
        bpy.context.scene.render.resolution_percentage = render_scale

    def __handle_svg(self, render_name):

        ## Rename svg to remove frame counting
        svg = render_name + '.svg'
        os.rename(render_name + FRAME + '.svg', svg)

        ## Remove svg not containing '<path'
        svg_content = get_file_content(svg)
        if '<path' not in svg_content:
            os.remove(svg)
        else:
            self.svgs.append(svg)

    def render(self, tmp_name, fs_linesets, obj):
        ''' Execute render for obj and save it as svg '''
        bpy.data.collections[tmp_name].objects.link(obj)
        bpy.context.scene.camera = self.obj
        render_condition = obj.hide_render
        obj.hide_render = False
        print('obj', obj.name)

        for ls in fs_linesets:
            render_name = self.folder_path  + os.sep + ls + os.sep + \
                    self.name + '-' + undotted(obj.name) + '_' + ls
            print('Render name:', render_name)
            fs_linesets[ls].show_render = True
            bpy.context.scene.render.filepath = render_name
            bpy.ops.render.render()
            fs_linesets[ls].show_render = False

            self.__handle_svg(render_name)
        
        bpy.data.collections[tmp_name].objects.unlink(obj)
        obj.hide_render = render_condition

    def set_back(self):
        ''' Invert cam direction to render back view '''
        bpy.ops.object.select_all(action='DESELECT')
        self.obj.select_set(True)
        bpy.context.view_layer.objects.active = self.obj

        bpy.ops.transform.resize(value=(1,1,-1), orient_type='LOCAL')
        bpy.ops.transform.translate(value=(0,0,2*self.obj.data.clip_start), 
                orient_type='LOCAL')

    def finalize(self):    
        self.dxfs = list(filter(None, 
            [svg2dxf(self.folder_path, svg_f) for svg_f in self.svgs]))
        subprocess.run([ODA_FILE_CONVERTER, self.folder_path, self.folder_path, 
            'ACAD2010', 'DWG', '1', '1', '*.dxf'])
        for d in self.dxfs:
            os.remove(d)
        self.dwgs = [re.sub('\.dxf$', '.dwg', dxf) for dxf in self.dxfs]
        
        print('dwgs:', self.dwgs)
        print('existing files:', self.existing_files)
        new_objs = list(set(self.dwgs) - set(self.existing_files))
        print('new files:', new_objs)
        if new_objs:
            self.__create_cad_script(new_objs)

    def __create_cad_script(self, new_objs):
        ''' Create script to run on cad file '''
        with open(self.script, 'a') as scr:
            ## Add new files only to script
            for new_obj in new_objs:
                rel_obj = new_obj.replace(RENDER_PATH,'').strip(os.sep)
                layer_name = re.search(LINESTYLE_LAYER_RE, rel_obj).group(1)
                scr.write('LAYER\nMA\n{}\n\nXREF\na\n{}\n0,0,0\n1\n1\n0\n'.format(
                    layer_name, rel_obj))
        scr.close()

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
        print('ls', ls)
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

def get_file_content(f):
    f = open(f, 'r')
    f_content = f.read()
    f.close()
    return f_content

def svg2dxf(folder_path, svg):
    ''' Convert svg to dxf '''
    render_path = os.path.splitext(svg)[0]
    eps = render_path + '.eps'
    dxf = render_path + '.dxf'

    eps2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(
        str(LARGE_RENDER_FACTOR), str(LARGE_RENDER_FACTOR)) + \
            "'dxf_s:-polyaslines -dumplayernames -mm' {} {}".format(eps, dxf)

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

def prepare_files(folder_path, cam_name):
    ''' Prepare files and folder to receive new renders '''
    existing_files = []
    if cam_name not in os.listdir(os.path.realpath(RENDER_PATH)):
        print('Create', folder_path)
        os.mkdir(folder_path)
        for fs in FREESTYLE_SETS:
            os.mkdir(folder_path + '/' + fs)
    else:
        ## Folder already exists. Get the dwgs inside it
        existing_files = [str(fi) for fi in list(
            Path(folder_path).rglob('*.dwg'))]
        print(folder_path, 'exists and contains:\n', existing_files)

    ## If dwg doesn't exist, copy it from blank template
    if cam_name + '.dwg' not in os.listdir(os.path.realpath(RENDER_PATH)):
        print('Create', folder_path + '.dwg')
        copyfile(BLANK_CAD, folder_path + '.dwg')
    else: 
        print(cam_name + '.dwg exists')

    return existing_files


def main():

    bpy.context.scene.render.resolution_x = RENDER_FACTOR * 1000
    bpy.context.scene.render.resolution_y = RENDER_FACTOR * 1000

    tmp_name = create_tmp_collection()
    fs_linesets = set_freestyle(tmp_name)
    print('fs_linesets', fs_linesets)

    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    bpy.context.scene.display.shading.light = 'FLAT'

    render_args = get_render_args()
    objs = render_args['objs']
    cams = []
    ## Create Cam objetcs
    for cam in render_args['cams']:
        cam_name = undotted(cam.name)
        folder_path = (RENDER_PATH + os.sep + cam_name).strip(os.sep)
        print(folder_path)
        cams.append(Cam(
            cam, cam_name, folder_path, 
            prepare_files(folder_path, cam_name),
            get_objects(cam) if not objs else objs
            ))

    for cam in cams:
        print('Objects to render are:\n', [ob.name for ob in cam.objects])
        cam.set_resolution()
        for obj in [ob for ob in cam.objects if ob not in DISABLED_OBJS]:
            cam.render(tmp_name, {fs_ls:fs_linesets[fs_ls] 
                for fs_ls in fs_linesets if fs_ls != 'bak'}, obj)

    ## Disable renderability for all objects to perform back renderings
    for obj in bpy.data.objects:
        obj.hide_render = True
    ## Render back views
    for cam in cams:
        cam.set_resolution()
        cam.set_back()
        for obj in [ob for ob in cam.objects if ob not in DISABLED_OBJS]:
            cam.render(tmp_name, {fs_ls:fs_linesets[fs_ls] 
                for fs_ls in fs_linesets if fs_ls == 'bak'}, obj)
        cam.set_back()
    ## Reset to original rendering condition
    for obj in bpy.data.objects:
        obj.hide_render = False if obj not in DISABLED_OBJS else True
    
    for cam in cams:
        cam.finalize()


main()
