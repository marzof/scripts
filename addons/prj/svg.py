#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 


import svgwrite
import svgutils
import xml.etree.ElementTree as ET
import numpy
import math
import re

frame_size_b_unit = 8.0
inch = 2.54
resolution = 96.0 ## px per inch
frame_size = frame_size_b_unit * resolution / inch
cut_id = 'blender_object_Line_Art'
frame_id = 'blender_object_frame_line_art'
svg_file = 'Wall_cut.svg'
is_cut = True

tuple_points = lambda x: [tuple([float(n) for n in i.split(',')]) 
        for i in x.split(' ')]

svg = svgutils.compose.SVG(svg_file)
frame_g = svg.find_id(frame_id)
element_g = svg.find_id(cut_id)
frame_pl = list(frame_g.root.iterdescendants('polyline'))
tuple_list = tuple_points(frame_pl[0].attrib['points'])

min_val = math.inf 
max_val = 0.0
for t in tuple_list:
    if sum(t) < min_val:
        min_val = sum(t)
        origin = t
    if sum(t) > max_val:
        max_val = sum(t)
        extension = t
dimension = numpy.subtract(extension, origin)
factor = frame_size / dimension[0]

drw = svgwrite.drawing.Drawing(filename='svgwrite.svg',
        size=(dimension[0] * factor, dimension[1] * factor))
group = drw.g()
pts_dict = {}
for i, pl in enumerate(list(element_g.root.iterdescendants('polyline'))):
    pts = tuple_points(pl.attrib['points'])
    new_pts = [tuple(numpy.multiply(numpy.subtract(p, origin), factor)) 
            for p in pts]
    two_points = [str(new_pts[0]), str(new_pts[1])]
    for po in two_points:
        if po not in pts_dict:
            pts_dict[po] = [i]
        else:
            pts_dict[po].append(i)
    print(i, new_pts)
print(pts_dict)
ordered_pts = []
i = 0
while len(pts_dict) > 0:
    for pt, idx in pts_dict.items():
        if i in idx:
            str_coords = re.findall('\d*\.\d*', pt)
            coords = [float(v) for v in str_coords]
            ordered_pts.append(coords)
            i = [v for v in pts_dict[pt] if v != i][0]
            break
    del(pts_dict[pt])
ordered_pts.append(ordered_pts[0])
print('ORDERED\n', ordered_pts)
polyline = drw.polyline(points = ordered_pts)
attrib = {'stroke': '#000000', 'stroke-opacity': '1', 'fill': 'none', 
        'stroke-linecap': 'round', 'stroke-width': '2', 'style': 'fill: #f00'}
polyline.update(attrib)
group.add(polyline)
drw.add(group)
drw.save(pretty=True)


