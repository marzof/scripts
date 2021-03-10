#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 


import svgwrite
import svgutils
import xml.etree.ElementTree as ET
import numpy
import math
import re


SCALE_FACTOR = 96.0 / 2.54 ## resolution / inch

tuple_points = lambda x: [tuple([float(n) for n in i.split(',')]) 
        for i in x.split(' ')]
get_g_polylines = lambda group: list(group.root.iterdescendants('polyline'))
get_pl_points = lambda polylines: [tuple_points(pt.attrib['points']) 
        for pt in polylines]


def read_svg(svg_file, obj, frame):
    svg = svgutils.compose.SVG(svg_file)
    frame_g = svg.find_id(frame)
    drawing_g = svg.find_id(obj)
    return svg, drawing_g, frame_g

def get_size(frame, frame_size):
    min_val = math.inf
    max_val = 0.0
    frame_pl = get_g_polylines(frame)
    frame_pts = get_pl_points(frame_pl)
    for pl in frame_pts:
        for co in pl:
            if sum(co) < min_val:
                min_val = sum(co)
                origin = co
            if sum(co) > max_val:
                max_val = sum(co)
                extension = co
    dimensions = numpy.subtract(extension, origin)
    factor = frame_size * SCALE_FACTOR / dimensions[0]
    return origin, dimensions, factor



def write_svg(svg, drawing_g, frame_g, frame_size, svg_path):
    origin, dimensions, factor = get_size(frame_g, frame_size)
    mm_factor = 10 * frame_size / dimensions[0]
    drw = svgwrite.drawing.Drawing(filename= svg_path + '.edit',
            size=(str(dimensions[0] * mm_factor) + 'mm', 
                str(dimensions[1] * mm_factor) + 'mm'))
    group = drw.g()
    pts_dict = {}
    for i, pl in enumerate(list(drawing_g.root.iterdescendants('polyline'))):
        #print('pl', pl)
        pts = tuple_points(pl.attrib['points'])
        #print('pts', pts)
        new_pts = [tuple(numpy.multiply(numpy.subtract(p, origin), factor)) 
                for p in pts]
        #print('new_pts', new_pts)
        two_points = [str(new_pts[0]), str(new_pts[1])]
        #print('two_points', two_points)
        four_coords = re.findall('\d*\.\d*', ''.join(two_points))
        coords = [tuple(four_coords[:2]), tuple(four_coords[2:])]
        #print(coords)

        polyline = drw.polyline(points = coords)
        attrib = {'stroke': '#000000', 'stroke-opacity': '1', 'id': 'pl',
                'stroke-linecap': 'round', 'stroke-width': '2'} #, 'style': 'fill: #f00'}
        polyline.update(attrib)
        group.add(polyline)
    drw.add(group)

## To join cut (continue) polylines
#        for po in two_points:
#            if po not in pts_dict:
#                pts_dict[po] = [i]
#            else:
#                pts_dict[po].append(i)
#        print(i, new_pts)
#    print(pts_dict)

#    ordered_pts = []
#    i = 0
#    while len(pts_dict) > 0:
#        for pt, idx in pts_dict.items():
#            if i in idx:
#                str_coords = re.findall('\d*\.\d*', pt)
#                coords = [float(v) for v in str_coords]
#                ordered_pts.append(coords)
#                i = [v for v in pts_dict[pt] if v != i][0]
#                break
#        del(pts_dict[pt])
#    ordered_pts.append(ordered_pts[0])
#    print('ORDERED\n', ordered_pts)
#    polyline = drw.polyline(points = ordered_pts)
#    attrib = {'stroke': '#000000', 'stroke-opacity': '1', 'id': 'pl',
#            'stroke-linecap': 'round', 'stroke-width': '2'} #, 'style': 'fill: #f00'}
#    polyline.update(attrib)
#    group.add(polyline)
#    drw.add(group)

    drw.save(pretty=True)

    #f = open(svg_path + '.edit', 'r')
    #svg = f.read()
    #f.close()
    #svg = re.sub('(<svg.*)>', r'\1%s' % sodipodi_insertion, svg, count=1)
    #f = open(svg_path + '.edit', 'w')
    #f.write(svg)
    #f.close()


