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
# TODO...

import sys
import prj
from prj import prj_svglib
from prj.prj_drawing_classes import Drawing_context, Draw_maker, Drawing_subject
from prj.prj_svglib import Svg_drawing, Layer, Path, Use, Style, SVG_ATTRIBUTES, PL_TAG
import time

start_time = time.time()

print('\n\n\n###################################\n\n\n')


ARGS: list[str] = [arg for arg in sys.argv[sys.argv.index("--") + 1:]]
ROUNDING: int = 3
SVG_ID = 'svg'
BASE_CSS = 'base.css'
svg_suffix = '.edit.svg'
svg_suffix = ''

def redraw_svg(subject: Drawing_subject, svg_size: tuple[str], factor: float,
        styles: list[str]) -> Svg_drawing:
    """ Create a new svg with layers (from groups) and path (from polylines)
        edited to fit scaled size and joined if cut """
    groups = prj_svglib.get_svg_groups(subject.svg_path, styles)
    css = f"@import url(../{BASE_CSS});"
    with Svg_drawing(subject.svg_path + svg_suffix, svg_size) as svg:
        svg.set_id(SVG_ID)
        style = svg.add_entity(Style, content = css) 
        for g in groups:
            layer_label = g.attrib['id']
            layer = svg.add_entity(Layer, label = layer_label) 
            layer.set_id(f'{subject.name}_{layer_label}')

            pl_coords = [prj_svglib.transform_points(pl.attrib['points'], 
                scale_factor=factor, rounding=ROUNDING) for pl in g.iter(PL_TAG)]

            if layer.label == 'cut':
                pl_coords = prj_svglib.join_coords(pl_coords)

            for coord in pl_coords:
                path = layer.add_entity(Path, 
                        coords_string = prj_svglib.get_path_coords(coord), 
                        coords_values = coord)
                path.add_class(layer_label)
                for collection in subject.collections:
                    path.add_class(collection)
                path.set_attribute(SVG_ATTRIBUTES[layer.label]) 
    return svg

def prepare_scene():
    pass


drawings: list[Svg_drawing] = []
subjects: list[Drawing_subject] = []
drawing_times = {}

draw_context = Drawing_context(args = ARGS)
draw_maker = Draw_maker(draw_context)

## TODO
## Prepare scene:
##     get visible objects by raycasting camera view 
##         or check by raycasting selected objects area
##     create plane with solidify mod at camera frame location and use it 
##         to create cuts (by boolean mod and solidify turned off) 
##         and cut objects (by boolean mod and solidify truned on)
##     make local and single user
##     use to_mesh() for curve (needed?)
##     use evaluated_get to take mods into account

for subject in draw_context.subjects:
    print('Drawing', subject.name)
    drawing_start_time = time.time()
    draw_subj = Drawing_subject(subject, draw_context)
    if draw_subj.visible:
        drawing = draw_maker.draw(draw_subj, draw_context.style)
        drawing_time = time.time() - drawing_start_time
        drawing_times[drawing_time] = subject.name
        print(f"   ...drawn in {drawing_times[drawing_time]} seconds")
        subjects.append(draw_subj)

for subject in subjects:
    svg = redraw_svg(subject, draw_context.svg_size, 
            draw_context.svg_factor, draw_context.svg_styles)
    drawings.append(svg)

with Svg_drawing(draw_context.camera.name, draw_context.svg_size) as composition:
    css = f"@import url({BASE_CSS});"
    style = composition.add_entity(Style, content = css) 
    for style in draw_context.svg_styles:
        layer = composition.add_entity(Layer, label = style)
        layer.set_id(style)
        for subject in subjects:
            use = layer.add_entity(Use, 
                    link = f'{subject.svg_path}{svg_suffix}#{subject.name}_{style}')
            use.set_id(subject.name)
            for collection in subject.collections:
                use.add_class(collection)

print("--- %s seconds ---" % (time.time() - start_time))
for t in sorted(drawing_times):
    print(t, drawing_times[t])


## SELECT ONLY ACTUAL VISIBLE OBJECTS
#### Select all objects in camera frame
#### Enter in edit mode for all objects
#### !! select_box everything is in camera frame -> not possible outside gui
#### get object with verts selected only

#import bpy, bpy_extras
#from mathutils import Vector
#from bpy_extras import view3d_utils, object_utils
#scene = bpy.context.scene
#cam = scene.camera
#
#for area in bpy.context.screen.areas:
#    if area.type == 'VIEW_3D':
#        for region in area.regions:
#            if region.type == 'WINDOW':
#                override = {'area': area, 'region': region} 
#                print(f'x:{region.x}, y:{region.y}, w:{region.width}, h:{region.height}')
#                rv3d = override['area'].spaces[0].region_3d
#                coord = bpy.data.objects[cam.name].location
#                coord_to_px = bpy_extras.view3d_utils.location_3d_to_region_2d(
#                        region, rv3d, coord)
#                px_to_coord = bpy_extras.view3d_utils.region_2d_to_location_3d(
#                        region, rv3d, Vector((0,0)), Vector((0,0,0)))
#                print('cam in 3dView at pixel', coord_to_px)
#                print('bottom left window corner in units', px_to_coord)
#                bpy.ops.view3d.select_box(override, xmin=0, xmax=10, ymin=50, ymax=100,
#                                    wait_for_input=False, mode='SET')
#                break
#        break
#print(len([vert for vert in bpy.data.objects['Floor.001'].data.vertices if vert.select]))
