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


STYLES = {
        'p': {'name': 'prj', 'occlusion_start': 0, 'occlusion_end': 0,
            'condition': 'is_in_front'},
        'c': {'name': 'cut', 'occlusion_start': 0, 'occlusion_end': 128,
            'condition': 'is_cut'},
        'h': {'name': 'hid', 'occlusion_start': 1, 'occlusion_end': 128,
            'condition': 'is_in_front'},
        }

drawing_styles = {}

def create_drawing_styles() -> None:
    """ Populate drawing_styles dict with Drawing_style objects """
    for s in STYLES:
        drawing_styles[s] = Drawing_style(style=s, name=STYLES[s]['name'], 
                occlusion_start=STYLES[s]['occlusion_start'],
                occlusion_end=STYLES[s]['occlusion_end'],
                condition=STYLES[s]['condition'])

class Drawing_style:

    def __init__(self, style: str, name: str, occlusion_start: int, 
            occlusion_end: int, condition: str):
        self.style = style
        self.name = name
        self.occlusion_start = occlusion_start
        self.occlusion_end = occlusion_end
        self.condition = condition

