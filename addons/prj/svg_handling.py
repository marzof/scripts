#!/usr/bin/env python3.9
# -*- coding: utf-8 -*- 

import os
from prj.svgread import Svg_read
from prj.svglib import AbsSvg_drawing, AbsStyle, AbsLayer, AbsUse
from prj.svglib import AbsPath, AbsGroup
from prj.utils import transform_points, get_path_coords, join_coords
from prj.drawing_camera import get_drawing_camera
from prj.drawing_style import drawing_styles

BASE_CSS = 'base.css'
SVG_ID = 'svg'
ROUNDING: int = 3

def prepare_obj_svg(context: 'Drawing_context', svg_path: 'Svg_path') \
        -> AbsSvg_drawing:
    """ Create an abstract version of object svg """

    files = {f['path']: {'obj':obj, 'data':f['data']} 
            for obj in svg_path.objects for f in svg_path.objects[obj]}
    css = f"@import url(../{BASE_CSS});"
    abssvg = AbsSvg_drawing(context.svg_size)
    abssvg.set_id(SVG_ID)
    absstyle = AbsStyle(content = css) 
    abssvg.add_entity(absstyle)

    abslayers = {}
    for drawing_style in context.svg_styles:
        abslayer = AbsLayer(label = drawing_style)
        abslayers[drawing_style] = abslayer
        abssvg.add_entity(abslayer)

    for f in files:
        obj = files[f]['obj']
        layer_label = files[f]['data']
        abslayer = abslayers[layer_label]
        absgroup = AbsGroup()
        absgroup.set_id(f'{obj.name}_{abslayer.label}')
        abslayer.add_entity(absgroup)
        is_cut = abslayer.label == 'cut'

        svg_read = Svg_read(f)
        abspaths = []
        all_points = []
        abspolylines = svg_read.get_svg_elements('polyline')
        for pl in abspolylines:
            pl.points = transform_points(pl.points, context.svg_factor, ROUNDING)
            all_points.append(pl.points[:])

        if is_cut:
            joined_points = join_coords(all_points)
            for coords in joined_points:
                abspath = AbsPath(coords_string = get_path_coords(coords), 
                        coords_values = coords)
                abspaths.append(abspath)
        else:
            for pl in abspolylines:
                abspath = AbsPath(coords_string = get_path_coords(pl.points),
                        coords_values = pl.points)
                abspaths.append(abspath) 

        for abspath in abspaths:
            abspath.add_class(layer_label)
            for collection in obj.collections:
                abspath.add_class(collection)
            absgroup.add_entity(abspath)

    #if 'cut' in context.svg_styles:
    #    clip_cut(layers['prj'], layers['cut'])

    for f in files:
        os.remove(f)

    return abssvg

def prepare_composition(context: 'Drawing_context', 
        subjects: list['Drawing_subject']) -> AbsSvg_drawing:
    """ Create an abstract version of composition svg """

    css = f"@import url({BASE_CSS});"
    abssvg = AbsSvg_drawing(context.svg_size)
    absstyle = AbsStyle(content = css) 
    abssvg.add_entity(absstyle)

    abslayers = {}
    absoverall_group = AbsGroup()
    absoverall_group.set_id('all')
    abssvg.add_entity(absoverall_group)
    for d_style in drawing_styles:
        drawing_style = drawing_styles[d_style].name
        abslayer = AbsLayer(label = drawing_style)
        abslayer.set_id(drawing_style)
        abslayers[drawing_style] = abslayer
        absoverall_group.add_entity(abslayer)
        ## TODO add actual styled links (not every objects has all styles)
        add_subjects_as_use(subjects, drawing_style, abslayers[drawing_style])
    return abssvg

def filter_subjects_for_svg(abstract_svg: Svg_read, 
        subjects: list['Drawing_subjects']) -> list['Drawing_subjects']:
    """ Check if subjects are in the abstrace_svg 
        and return the ones which are not there """
    use_objects = abstract_svg.get_svg_elements('use')
    use_subj_names = list(set([use.attributes['xlink:title'] \
            for use in use_objects]))
    new_subjects = [subj for subj in subjects if subj.name not in use_subj_names]
    return new_subjects

def add_subjects_as_use(subjects: list['Drawing_subject'], style: str, 
        container: 'AbsSvg_container') -> None:
    """ Create use elements for every subject and add to abs_svg"""
    draw_camera = get_drawing_camera()
    for subject in subjects:
        link = f'{draw_camera.name}{os.sep}{subject.name}.svg'
        link += f'#{subject.name}_{style}'
        new_use = AbsUse(link)
        new_use.set_id(f'{subject.name}_{style}')
        new_use.set_attribute({'xlink:title': subject.name})
        for collection in subject.collections:
            new_use.add_class(collection)
        container.add_entity(new_use)
