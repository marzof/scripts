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

# TODO
# - add some instructions
# - fix how object occluded by cut surfaces are rendered if cut object 
#   are not included in rendering

import bpy
import os, sys
import re, random
import collections
import subprocess, shlex
from shutil import copyfile
from pathlib import Path
import ezdxf
import mathutils
from mathutils import Vector
from mathutils import geometry
from mathutils import Matrix
from bpy_extras.object_utils import world_to_camera_view

import time

start_time = time.time()

check_list = lambda x, alt: x if x else alt
undotted = lambda x: x.replace('.', '_')
norm_path = lambda x: os.path.realpath(x).replace(
        os.path.realpath('.'), '').strip(os.sep)

ARGS = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
FLAGS = [arg for arg in ARGS if arg.startswith('-')]
BLANK_CAD = './blank.dwg'
STATUS = 'status'
ODA_FILE_CONVERTER = '/usr/bin/ODAFileConverter'
LINESTYLE_LAYER_RE = r'.*(_.*)\.dwg'
FACTOR_MARKER = '-f'
ADD_SCRIPT_MARKER = '-add'
SCRIPT_MODE = 'a' if ADD_SCRIPT_MARKER in FLAGS else 'w'
SCRIPTS = [{'name': 'xrefs.scr', 'mode': 'a'}, 
        {'name': 'last_xrefs.scr', 'mode': SCRIPT_MODE}]
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
FREESTYLE_SETTINGS = bpy.context.window.view_layer.freestyle_settings
## Set by UI
## FREESTYLE_CREASE_ANGLE = 2.6179938316345215 ## 150°
## FREESTYLE_USE_SMOOTHNESS = True 
## FREESTYLE_SETTINGS.crease_angle = FREESTYLE_CREASE_ANGLE
## FREESTYLE_SETTINGS.use_smoothness = FREESTYLE_USE_SMOOTHNESS
FREESTYLE_SETS = {
        'prj': { 'flag': 'p', 'visibility': 'VISIBLE', 'silhouette': True, 
            'border': True, 'contour': True, 'crease': True, 'mark': True },
        'cut': { 'flag': 'c', 'visibility': 'VISIBLE', 'silhouette': False, 
            'border': True, 'contour': False, 'crease': False, 'mark': False },
        'hid': { 'flag': 'h', 'visibility': 'HIDDEN', 'silhouette': True, 
            'border': True, 'contour': True, 'crease': True, 'mark': True },
        'bak': { 'flag': 'b', 'visibility': 'VISIBLE', 'silhouette': True, 
            'border': True, 'contour': True, 'crease': True, 'mark': True },
        }
FREESTYLE_SETS_DEFAULT = ['prj', 'cut']
RENDERABLE_STYLES = check_list([ls for ls in FREESTYLE_SETS if 
    FREESTYLE_SETS[ls]['flag'] in list(''.join(FLAGS))], 
    [ls for ls in FREESTYLE_SETS_DEFAULT])
RENDER_PATH = norm_path(bpy.context.scene.render.filepath)

BOUNDING_BOX_EDGES = ((0, 1), (0, 3), (0, 4), (1, 2), (1, 5), (2, 3), 
                    (2, 6), (3, 7), (4, 5), (4, 7), (5, 6), (6, 7))

BOUNDING_BOX_FACES = ((0, 1, 2, 3), (2, 3, 7, 6), (6, 7, 4, 5),
                   (4, 5, 1, 0), (0, 4, 7, 3), (1, 5, 6, 2)) 

FRAME_EDGES = (Vector((0,0)), Vector((1,0)), Vector((1,1)), Vector((0,1)))
EXTRUDE_CUT_FACTOR = .005

print('\n\n\n###################################\n\n\n')

print('flags', FLAGS)
print('script mode', SCRIPT_MODE)
print('Render factor', LARGE_RENDER_FACTOR)
print('Renderable styles', RENDERABLE_STYLES)

class Cam():
    def __init__(self, obj, name, folder_path, existing_files, objects):
        self.obj = obj
        self.name = name
        self.folder_path = folder_path
        self.scripts = [self.folder_path + os.sep + SCRIPTS[0]['name'], 
                self.folder_path + os.sep + SCRIPTS[1]['name']]
        self.existing_files = existing_files
        self.objects = objects['all']
        self.frontal_objects = objects['frontal']
        self.behind_objects = objects['behind']
        self.cut_objects = {}
        self.svgs = []
        self.dxfs = []
        self.dwgs = []
        self.view_frame = [v * Vector((1,1,obj.data.clip_start)) 
                for v in obj.data.view_frame()]
        self.frame = [obj.matrix_world @ v for v in self.view_frame]
        self.dir = mathutils.geometry.normal(self.frame[:3])
        self.frame_loc = (self.frame[0] + self.frame[2]) / 2

    def set_resolution(self):
        ''' Set resolution for camera '''
        ## 100% if cam ortho scale == base ortho scale
        render_scale = round(100 * self.obj.data.ortho_scale/BASE_ORTHO_SCALE)
        bpy.context.scene.render.resolution_percentage = render_scale

    def create_cut(self):
        ''' Duplicate, bisect and extrude cut objects '''
        bpy.ops.object.select_all(action='DESELECT')
        cut_objs = [ob for ob in self.frontal_objects 
                if ob in self.behind_objects]
        for ob in cut_objs:
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
            print('duplicate', ob.name, 'for cutting object')
            bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
            if ob.type == 'EMPTY' or ob.override_library:
                contained_objects = make_local(bpy.context.object)
                cleaned_objects = self.__clean_and_prepare(contained_objects, ob)
            elif ob.type == 'CURVE':
                bpy.ops.object.convert(target='MESH')
                apply_mod(ob, type=['EDGE_SPLIT', 'MIRROR', 'SUBSURF', 'SOLIDIFY', 'BEVEL'])
            else:
                apply_mod(ob, type=['EDGE_SPLIT', 'MIRROR', 'SUBSURF', 'SOLIDIFY', 'BEVEL'])

            new_ob = bpy.context.selected_objects
            self.cut_objects[ob] = new_ob
            if new_ob:
                print('Ready to bisect', new_ob, 'of', ob.name)
                self.__bisect_and_extrude()
            for sel_ob in new_ob:
                sel_ob.select_set(False)
            bpy.ops.object.select_all(action='DESELECT')

    def __clean_and_prepare(self, all_objects, ref_obj):
        ''' Remove not framed objects, apply modifiers and join the remaining '''
        to_delete = []
        to_join = []
        ## Remove not framed objects from empty
        for ob in all_objects:
            framed = in_frame(self.obj, ob, ref_obj)
            if framed['framed'] and framed['frontal'] and framed['behind']:
                print('to keep', ob.name)
                print('prepare to join', ob.name)
                to_join.append(ob)
                ## Make single user for multi-user objects
                if ob.data.users > 1:
                    ob.data = ob.data.copy()
                ob.select_set(True)
                bpy.context.view_layer.objects.active = ob
                apply_mod(ob, type=['EDGE_SPLIT', 'MIRROR', 'SUBSURF', 'SOLIDIFY', 'BEVEL'])
            else:
                print('to delete', ob.name)
                to_delete.append(ob)
        bpy.ops.object.select_all(action='DESELECT')
        for ob in to_delete:
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
        bpy.ops.object.delete(use_global=False)
        bpy.ops.object.select_all(action='DESELECT')
        for ob in to_join: 
            print('to join', ob.name)
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
            if ob.type == 'CURVE':
                print('Convert curve to mesh')
                bpy.ops.object.convert(target='MESH')

        return bpy.context.selected_objects

    def __bisect_and_extrude(self):
        ''' Enter in edit mode, bisect by cam frame and extrude front and rear '''
        bpy.ops.object.editmode_toggle()
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.select_mode(use_extend=False, use_expand=False, 
                type='VERT')
                
        bpy.ops.mesh.bisect(plane_co=self.frame_loc, plane_no=self.dir,
            use_fill=True, clear_inner=True, clear_outer=True)

        bpy.ops.mesh.extrude_region_move(
            MESH_OT_extrude_region={"use_normal_flip":False, "mirror":False},
            TRANSFORM_OT_translate={"value":self.dir * EXTRUDE_CUT_FACTOR})
        bpy.ops.mesh.select_all(action='INVERT')
        bpy.ops.mesh.extrude_region_move(
            MESH_OT_extrude_region={"use_normal_flip":False, "mirror":False},
            TRANSFORM_OT_translate={"value":-self.dir * EXTRUDE_CUT_FACTOR})

        bpy.ops.object.editmode_toggle()

    def delete_cut(self):
        ''' Remove created cut object '''
        for ob in self.cut_objects:
            actual_obj = self.cut_objects[ob]
            for inner_obj in actual_obj:
                inner_obj.select_set(True)
                bpy.context.view_layer.objects.active = inner_obj
                bpy.data.objects.remove(inner_obj, do_unlink=True) 

    def render(self, tmp_name, fs_linesets, obj):
        ''' Execute render for obj and save it as svg '''
        bpy.context.scene.camera = self.obj
        actual_obj = [obj]

        for ls in fs_linesets:
            print('Start rendering', obj.name, 'with style', ls)
            status_file = open(self.folder_path + os.sep + STATUS, 'a')
            status_file.write('\nStart rendering {} with style {}'.format(
                obj.name, ls))
            ## Cut render only for actual cut objects
            if ls == 'cut':
                if obj in self.cut_objects:
                    actual_obj = self.cut_objects[obj]
                else:
                    return
            elif obj.type == 'EMPTY':
                obj.select_set(True)
                bpy.context.view_layer.objects.active = obj
                bpy.ops.object.duplicate(linked=False, mode='TRANSLATION')
                actual_obj = make_local(bpy.context.object)

            for act_ob in actual_obj:
                bpy.data.collections[tmp_name].objects.link(act_ob)
                render_condition = act_ob.hide_render
                act_ob.hide_render = False

            render_name = self.folder_path  + os.sep + ls + os.sep + \
                    self.name + '-' + undotted(obj.name) + '_' + ls
            print('Render name:', render_name)
            fs_linesets[ls].show_render = True
            bpy.context.scene.render.filepath = render_name
            bpy.ops.render.render()
            status_file.write('\n\t...render completed!')
            status_file.close()
            fs_linesets[ls].show_render = False

            self.__handle_svg(render_name)
        
            for coll_obj in bpy.data.collections[tmp_name].objects:
                bpy.data.collections[tmp_name].objects.unlink(coll_obj)
                coll_obj.hide_render = render_condition

    def __handle_svg(self, render_name):
        ''' Rename and clean up svg '''
        
        ## Rename svg to remove frame counting
        svg = render_name + '.svg'
        os.rename(render_name + FRAME + '.svg', svg)

        ## Remove svg not containing '<path'
        svg_content = get_file_content(svg)
        if '<path' not in svg_content:
            status_file = open(self.folder_path + os.sep + STATUS, 'a')
            status_file.write('\n{} not visible'.format(svg))
            status_file.close()
            print('Void SVG!!')
            os.remove(svg)
        else:
            self.svgs.append(svg)

    def set_back(self):
        ''' Invert cam direction to render back view '''
        bpy.ops.object.select_all(action='DESELECT')
        self.obj.select_set(True)
        bpy.context.view_layer.objects.active = self.obj

        bpy.ops.transform.resize(value=(1,1,-1), orient_type='LOCAL')
        bpy.ops.transform.translate(value=(0,0,2*self.obj.data.clip_start), 
                orient_type='LOCAL')

    def finalize(self):    
        ''' Convert svg to dwg and write script to embed xref to dwg'''
        self.dxfs = list(filter(None, 
            [svg2dxf(svg_f) for svg_f in self.svgs]))
        subprocess.run([ODA_FILE_CONVERTER, self.folder_path, self.folder_path, 
            'ACAD2010', 'DWG', '1', '1', '*.dxf'])
        for d in self.dxfs:
            if os.path.exists(d):
                os.remove(d)
        self.dwgs = [re.sub('\.dxf$', '.dwg', dxf) for dxf in self.dxfs]
        
        print('dwgs:', self.dwgs)
        #print('existing files:', self.existing_files)
        new_objs = list(set(self.dwgs) - set(self.existing_files))
        print('\n\nnew files:', new_objs)
        if new_objs:
            self.__create_cad_script(new_objs)

    def __create_cad_script(self, new_objs):
        ''' Create script to run on cad file '''
        for i, script in enumerate(self.scripts):
            with open(script, SCRIPTS[i]['mode']) as scr:
                self.__write_script(scr, new_objs)
            scr.close()

    def __write_script(self, scr, new_objs):
        ''' Write script for embedding xref in the right layers '''
        for new_obj in new_objs:
            rel_obj = new_obj.replace(RENDER_PATH,'').strip(os.sep)
            layer_name = re.search(LINESTYLE_LAYER_RE, rel_obj).group(1)
            scr.write('LAYER\nM\n{}\n\nXREF\na\n{}\n0,0,0\n1\n1\n0\n'.format(
                layer_name, rel_obj))
        scr.write('LAYER\nM\n0\n\n')

##### UTILITIES #####

def get_file_content(f):
    ''' Get the content from file f '''
    f = open(f, 'r')
    f_content = f.read()
    f.close()
    return f_content

def svg2dxf(svg):
    ''' Convert svg to dxf '''
    render_path = os.path.splitext(svg)[0]
    eps = render_path + '.eps'
    dxf = render_path + '.dxf'

    eps2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(
        str(LARGE_RENDER_FACTOR), str(LARGE_RENDER_FACTOR)) + \
            "'dxf_s:-polyaslines -dumplayernames -mm' {} {}".format(eps, dxf)

    ## Run with Inkscape 0.92
    #subprocess.run(['inkscape', '-f', svg, '-C', '-E', eps])
    ## Run with Inkscape 1.0
    subprocess.run(['inkscape', svg, '-C', '-o', eps])

    if os.path.exists(svg):
        os.remove(svg)

    subprocess.run(eps2dxf, shell=True) 
    if os.path.exists(eps):
        os.remove(eps)

    ## Convert dxf to readable code page (utf-8 -> DWGCODEPAGE ANSI_1252)
    ## and set linetype and lineweight to 'ByBlock'
    dxf_file = ezdxf.readfile(dxf, 'utf-8')
    for entity in dxf_file.modelspace().query('LINE'):
        entity.dxf.linetype = 'ByBlock'
        entity.dxf.lineweight = -2
    dxf_file.saveas(dxf)

    return dxf

def apply_mod(obj, type = []):
    ''' Apply modifier of type "type" '''

    ## Remove shape keys
    ## TODO apply the active shape key after the other to keep the shape
    if obj.data.shape_keys:
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.shape_key_remove(all=True)
        print('remove shape_key', obj.data.shape_keys)

    mods = [mod for mod in obj.modifiers if mod.type in type and mod.show_render]
    for mod in mods:
        bpy.ops.object.modifier_apply(modifier=mod.name)

def make_local(obj):
    ''' Convert linked object to local object '''
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.duplicates_make_real(use_base_parent=False, 
            use_hierarchy=False)
    all_objects = bpy.context.selected_objects
    print('made local', all_objects)
    bpy.ops.object.select_all(action='DESELECT')
    for ob in all_objects:
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.make_local(type='SELECT_OBDATA')
    return all_objects

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
            intersect = mathutils.geometry.intersect_point_quad_2d(
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

##### OPS #####

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
    ## Disable existing linesets
    for ls in FREESTYLE_SETTINGS.linesets:
        ls.show_render = False

    ## Create dedicated linesets
    linesets = {}
    for ls in [fs for fs in FREESTYLE_SETS if fs in RENDERABLE_STYLES]:
        print('ls', ls)
        linesets[ls] = FREESTYLE_SETTINGS.linesets.new(tmp_name + '_' + ls)
        linesets[ls].show_render = False
        linesets[ls].select_by_collection = True
        linesets[ls].collection = bpy.data.collections[tmp_name]
        linesets[ls].visibility = FREESTYLE_SETS[ls]['visibility']
        linesets[ls].select_silhouette = FREESTYLE_SETS[ls]['silhouette']
        linesets[ls].select_border = FREESTYLE_SETS[ls]['border']
        linesets[ls].select_contour = FREESTYLE_SETS[ls]['contour']
        linesets[ls].select_crease = FREESTYLE_SETS[ls]['crease']
        linesets[ls].select_edge_mark = FREESTYLE_SETS[ls]['mark']

    return linesets

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
        ## Copy dwg from blank template
        print('Create', folder_path + '.dwg')
        copyfile(BLANK_CAD, folder_path + '.dwg')
    else:
        ## Folder already exists. Get the dwgs inside it
        existing_files = [str(fi) for fi in list(
            Path(folder_path).rglob('*.dwg'))]
        print(folder_path, 'exists and contains:\n', existing_files)
        file_in_folder = cam_name + '.dwg' in os.listdir(
                os.path.realpath(RENDER_PATH))
        print(cam_name + '.dwg ' + ("NOT " * (not file_in_folder)) + 'in ' + 
                folder_path)
        if not file_in_folder:
            print('Create', folder_path + '.dwg')
            copyfile(BLANK_CAD, folder_path + '.dwg')

    return existing_files

def viewed_objects(cam, objs):
    """ Filter objects to collect """
    objects = []
    frontal_objs = []
    behind_objs = []
    referenced_objs = {}
    ## Use indicate objects (as args or selected) if any. Else use selectable
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

def get_non_case_sensitive_same_name(cam):
    ''' Check if same name objects are present in object to render
        or in render folder '''
    same_name = [item for item, count in collections.Counter(
        [ob.name.lower() for ob in cam.objects]).items() if count > 1]
    if same_name:
        return same_name
    else:
        existing_file_objects = []
        for f in cam.existing_files:
            ## Based on render_name of Cam.render()
            start_index = f.rfind(cam.name) + len(cam.name + '-')
            end_index = f.rfind('_')
            existing_file_objects.append(f[start_index: end_index])
        lower_exist_file_objs = [fo.lower() for fo in existing_file_objects]
        for ob in cam.objects:
            ## Get objects with same name but different in upper and lower-case
            if ob.name.lower() in lower_exist_file_objs and \
                    ob.name not in existing_file_objects:
                        same_name.append(ob.name + ' (check files)')
    return same_name


def main():

    bpy.context.scene.render.resolution_x = RENDER_FACTOR * 1000
    bpy.context.scene.render.resolution_y = RENDER_FACTOR * 1000
    bpy.context.scene.render.engine = 'BLENDER_WORKBENCH'
    bpy.context.scene.display.shading.light = 'FLAT'
    bpy.context.scene.render.use_freestyle = True
    bpy.context.scene.svg_export.use_svg_export = True

    tmp_name = create_tmp_collection()
    fs_linesets = set_freestyle(tmp_name)
    render_args = get_render_args()
    print('fs_linesets', fs_linesets)

    objs = render_args['objs']
    cams = []
    ## Create Cam objetcs
    for cam in render_args['cams']:
        cam_name = undotted(cam.name)
        folder_path = (RENDER_PATH + os.sep + cam_name).strip(os.sep)
        print('folder path', folder_path)
        cams.append(Cam(
            cam, cam_name, folder_path, 
            prepare_files(folder_path, cam_name),
            viewed_objects(cam, objs)))
        print('objects are', cams[-1].objects)

    for cam in cams:
        same_name_objects = get_non_case_sensitive_same_name(cam)
        if same_name_objects:
            print('The following objects have the same name for non ' + \
                    'case-sensitive os. \nPlease fix it before continuing')
            print(same_name_objects)
            return
        print('Objects to render are:\n', [ob.name for ob in cam.objects])
        print('Frontal are:\n', [ob.name for ob in cam.frontal_objects])
        print('Behind are:\n', [ob.name for ob in cam.behind_objects])
        status_file = open(folder_path + os.sep + STATUS, 'w')
        status_file.write('\nObjects to render are {}:\n{}'.format(
            len(cam.objects), [ob.name for ob in cam.objects]))
        status_file.write('\nFrontal objects are {}:\n{}'.format(
            len(cam.frontal_objects), [ob.name for ob in cam.frontal_objects]))
        status_file.write('\nBehind objects are {}:\n{}'.format(
            len(cam.behind_objects), [ob.name for ob in cam.behind_objects]))
        cam.set_resolution()
        cam.create_cut()
        status_file.write('\nCut objects are {}:\n{}'.format(
            len(cam.cut_objects), [ob.name for ob in cam.cut_objects]))
        status_file.close()
        for i, obj in enumerate([ob for ob in cam.frontal_objects 
                if ob not in DISABLED_OBJS], start=1):
            status_file = open(folder_path + os.sep + STATUS, 'a')
            status_file.write('\nRender {}, object #{}/{} ({}%)'.format(
                obj.name, i, len(cam.frontal_objects), 
                round(100 * float(i)/len(cam.frontal_objects), 2)))
            status_file.close()
            cam.render(tmp_name, {fs_ls:fs_linesets[fs_ls] 
                for fs_ls in fs_linesets if fs_ls != 'bak'}, obj)
        cam.delete_cut()

    ## Disable renderability for all objects to perform back renderings
    for obj in bpy.context.selectable_objects:
        obj.hide_render = True
    ## Render back views
    if 'bak' in fs_linesets.keys():
        for cam in cams:
            cam.set_resolution()
            cam.set_back()
            for obj in [ob for ob in cam.behind_objects if ob not in DISABLED_OBJS]:
                cam.render(tmp_name, {'bak':fs_linesets['bak']}, obj)
            cam.set_back()
    ## Reset to original rendering condition
    for obj in bpy.context.selectable_objects:
        obj.hide_render = False if obj not in DISABLED_OBJS else True

    for cam in cams:
        cam.finalize()


main()
print("--- %s seconds ---" % (time.time() - start_time))
