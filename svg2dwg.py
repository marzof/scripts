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


import sys
from pathlib import Path
import subprocess, shlex
import re

oda_file_converter = '/usr/bin/ODAFileConverter'

scale_factor = 1
factor_marker = '-f'
#if factor_marker in args:
#    factor_index = args.index(factor_marker) + 1 
#    scale_factor = int(args[factor_index])
#    print('### Render factor:', large_render_factor)
#    del args[factor_index - 1 : factor_index + 1]


def svg2dwg(path):
    filename = path.stem
    svg = filename + '.svg'
    eps = filename + '.eps'
    dxf = filename + '.dxf'

    subprocess.run(['inkscape', svg, '-C', '-o', eps])

    svg2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(str(scale_factor),
            str(scale_factor)) + "'dxf_s:-polyaslines -ctl -mm' {} {}".format(
                    eps, dxf)
    subprocess.run(svg2dxf, shell=True) 

    subprocess.run([oda_file_converter, path.parents[0], path.parents[0], 
        'ACAD2013', 'DWG', '1', '1', filename + '.dxf'])
    subprocess.run(['rm', eps, dxf])

def main():
    #args = [arg for arg in sys.argv] #[sys.argv.index("--") + 1:]]
    f = sys.argv[1]
    path = Path(f)

    svg2dwg(path)

main()


