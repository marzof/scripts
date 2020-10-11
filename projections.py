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

oda_file_converter = '/usr/bin/ODAFileConverter'
active = bpy.context.view_layer.objects.active
large_render_factor = 1

tmp_name = ''

frame = "{:04d}".format(bpy.context.scene.frame_current)
renders_paths = []

dxfmerge_path = '/home/mf/softwares/qcad-pro/merge' 

re_block = r"^BLOCK$[^\*]+?^AcDbBlockEnd$"
re_block_begin = r"^AcDbBlockBegin\n\s*?2\n(.+)\n\s*?70\n\s*(\w+)\n"
re_block_body = lambda x: r"^"+ x +"\n\s*?1\n([^*]*)?\n\s*0\nENDBLK"
xref_code = '100'
dxf_extension = 'dxf'

path = bpy.context.scene.render.filepath
args = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
selection = bpy.context.selected_objects

def create_tmp_collection():
    """ Create a tmp collection and link it to the actual scene """
    global tmp_name
    ## Set a random name for the render collection
    hash_code = random.getrandbits(32)
    collection_name = '%x' % hash_code
    while collection_name in [coll.name for coll in bpy.data.collections]:
        hash_code = random.getrandbits(32)
        collection_name = '%x' % hash_code

    tmp_name = collection_name
    render_collection = bpy.data.collections.new(tmp_name)
    bpy.context.scene.collection.children.link(render_collection)
    print('Created tmp collection', tmp_name) 
    print(render_collection) 

def set_freestyle():
    ''' Enable Freestyle and set lineset and style for rendering '''
    bpy.context.scene.render.use_freestyle = True
    bpy.context.scene.svg_export.use_svg_export = True
    fs_settings = bpy.context.window.view_layer.freestyle_settings
    fs_settings.linesets.new(tmp_name)
    for lineset in fs_settings.linesets:
        lineset.show_render = False

    fs_lineset = fs_settings.linesets[-1]
    fs_lineset.name = tmp_name
    fs_lineset.show_render = True
    fs_lineset.select_by_collection = True
    fs_lineset.collection = bpy.data.collections[tmp_name]

    print('Created tmp lineset', fs_lineset.name)
    print(fs_settings.linesets[tmp_name])

def get_objects():
    """ Filter objects to collect """
    ## TODO set to just rendered objects
    objs = []
    for obj in bpy.context.selectable_objects:
        if obj.type not in ['MESH', 'CURVE']:
            continue
        objs.append(obj)
    return objs

def render_cam(cam, folder_path):
    global renders_paths
    
    for obj in get_objects():
        render_filename = folder_path  + '/' + obj.name
        print('render_filename', render_filename)
        
        bpy.data.collections[tmp_name].objects.link(obj)

        bpy.context.scene.render.filepath = render_filename
        bpy.context.scene.camera = cam
        bpy.ops.render.render()
        
        bpy.data.collections[tmp_name].objects.unlink(obj)

        ## Rename svg to remove frame counting
        subprocess.run('mv ' + render_filename + frame + '.svg ' + \
            render_filename + '.svg', shell=True)

        renders_paths.append(render_filename)
    
def svg2dxf(render_path, folder_path):
    ''' Convert svg to dxf '''
    svg = render_path + '.svg'
    eps = render_path + '.eps'
    dxf = render_path + '.dxf'

    ## Run with Inkscape 0.92
    subprocess.run(['inkscape', '-f', svg, '-C', '-E', eps])

    ## Run with Inkscape 1.0
    ## subprocess.run(['inkscape', svg, '-C', '-o', eps])

    eps2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(
            str(large_render_factor), str(large_render_factor)) + \
                    "'dxf_s:-polyaslines -dumplayernames -mm' {} {}".format(eps, dxf)
    subprocess.run(eps2dxf, shell=True) 
    subprocess.run(['rm', svg, eps])

def merge_dxf(renders_paths, folder_path):
    ''' Create the xml for dxf merging '''
    print("Create xml for dxfs merging")
    xml_opening = '<?xml version="1.0" encoding="UTF-8"?> \
            \n\t<merge xmlns="http://qcad.org/merge/elements/1.0/" unit="Millimeter">'
    xml_item = lambda x: '\n\t\t<item src="' + x + '.dxf"><insert></insert></item>'
    xml_close = '\n\t</merge>'
    xml_body = xml_opening + \
            ''.join([xml_item(d) for d in renders_paths]) + xml_close
    xml_path = folder_path + '.xml'
    xml_file = open(xml_path, 'w')
    xml_file.write(xml_body)
    xml_file.close()
    print("Merging done")

    ## Merge all dxfs in one
    merging_parameters = '-f -o ' + folder_path + '.dxf ' + xml_path
    subprocess.call(dxfmerge_path + ' ' + merging_parameters, shell=True)
    subprocess.run(['rm', xml_path])

def blocks2xref(folder_path):
    ''' Convert every block inside dxf in xref '''
    f = open(folder_path + '.' + dxf_extension, 'r')
    dxf = f.read()
    f.close()

    blocks = re.findall(re_block, dxf, re.MULTILINE)

    for b in blocks:
        block_begin_src = re.search(re_block_begin, b, re.MULTILINE)
        block_name = block_begin_src.group(1).strip()
        block_type = block_begin_src.group(2)
        type_start = block_begin_src.span(2)[0]
        type_end = block_begin_src.span(2)[1]
        begin_end = block_begin_src.span(0)[1]

        block_body_src = re.search(re_block_body(block_name), b[begin_end:], 
                re.MULTILINE)
        block_body = block_body_src.group(1)
        body_start = begin_end + block_body_src.span(1)[0]
        body_end = begin_end + block_body_src.span(1)[1]

        new_block = b[:type_start] + xref_code + b[type_end:body_start] + folder_path + \
                '/' + block_name + '.' + dxf_extension + b[body_end:]

        dxf = re.sub(b, new_block, dxf, re.MULTILINE)

    f = open(folder_path + '.' + dxf_extension, 'w')
    f.write(dxf)
    f.close()

def main():
    ## Get the cameras
    ## TODO get objects too: allowing partial rendering
    if not args:
        cams = [obj for obj in selection if obj.type == 'CAMERA']
    else:
        cams = [bpy.data.objects[arg] for arg in args]

    create_tmp_collection()
    set_freestyle()
    for cam in cams:
        folder_path = path + cam.name

        ## Try to create the folder for objects drawings.
        ## If it exists go on and rewrite files inside it
        ## TODO check all the files already in folder and compare with new files
        try:
            os.mkdir(folder_path)
        except:
            pass

        render_cam(cam, folder_path)

        for render_path in renders_paths:
            ## TODO convert to dwg and delete unnecessary files
            svg2dxf(render_path, folder_path)
        ## TODO create a script to populate the dwg with xref
        if not os.path.exists(folder_path + '.' + dxf_extension):
            merge_dxf(renders_paths, folder_path)
            blocks2xref(folder_path)

main()
