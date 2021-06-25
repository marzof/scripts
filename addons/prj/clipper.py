#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import svgwrite
from svgwrite import cm, mm
import pyclipper
import xml.etree.ElementTree as ET

path = '/home/mf/Documents/TODO/svg_composition/test_clipper.svg'

draw = svgwrite.drawing.Drawing(filename= path, size=('100mm','100mm'))

g_proj = draw.g(id='proj')

subj = [
    [[20,20], [320,20], [320,320], [20,320], [20,20]],
    [[20,20], [320,320]],
    [[320,20], [20,320]]
    ]
clip = [
        [[100,100], [240,100], [240,240], [100,240]],
        [[300,300], [350,300], [350,350], [300,350]]
        ]
pc = pyclipper.Pyclipper()
pc.AddPaths(clip, pyclipper.PT_CLIP, True)
pc.AddPaths(subj, pyclipper.PT_SUBJECT, False)
solution = pc.Execute2(pyclipper.CT_DIFFERENCE)
#print('solution depth', solution.depth) 
#print('child len', len(solution.Childs)) 
contours = [child.Contour for child in solution.Childs]
for coords in contours:
    c = f'M {coords[0][0]},{coords[0][1]} '
    c += ' '.join([f'L {co[0]},{co[1]}' for co in coords[1:]])
    g_proj.add(draw.path(d=c, stroke='red', fill='none'))
draw.add(g_proj)

g_cut = draw.g(id='cut')
pA = draw.path(d='M 100,100 L 240,100 L 240,240 L 100,240 z', stroke='blue', fill='none')
pB = draw.path(d='M 300,300 L 350,300 L 350,350 L 300,350 z', stroke='blue', fill='none')
g_cut.add(pA)
g_cut.add(pB)
draw.add(g_cut)

ET.register_namespace('prj',"https://github.com/marzof/scripts")
root = ET.Element("{https://github.com/marzof/scripts}prj")
body = ET.SubElement(root, "{https://github.com/marzof/scripts}bound_rect")
body.text = '((0.5, 0.0), (1.0, 0.4))'
draw.set_metadata(root)

draw.save(pretty=True)

