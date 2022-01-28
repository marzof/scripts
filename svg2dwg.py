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


import sys, os
from pathlib import Path
import subprocess, shlex
import re

oda_file_converter = '/usr/bin/ODAFileConverter'
scale_marker = '-s'
scale_re = re.compile("(\d*)[:\/](\d*)")

def svg2dwg(path: Path, scale_factor: float) -> None:
    output_path = Path(path.parents[0]) / "DWGS"
    output_path.mkdir(parents=True, exist_ok=True)
    filename = path.stem
    svg = filename + '.svg'
    eps = str(output_path) + os.sep + filename + '.eps'
    dxf = str(output_path) + os.sep + filename + '.dxf'

    subprocess.run(['inkscape', svg, '-C', '-o', eps])

    svg2dxf = "pstoedit -xscale {} -yscale {} -dt -f ".format(str(scale_factor),
            str(scale_factor)) + "'dxf_14:-polyaslines -ctl -mm' {} {}".format(
                    eps, dxf)
    subprocess.run(svg2dxf, shell=True) 
    dxf_f = open(dxf, 'r')
    dxf_content = dxf_f.read()
    fixed_dxf_content = re.sub('\$LUNITS.*\n(\s*70).*\n(\s*)4', 
            r'$LUNITS\n\g<1>\n\g<2>2', dxf_content, flags = re.MULTILINE)
    dxf_f.close()
    fixed_dxf = open(dxf, 'w')
    fixed_dxf.write(fixed_dxf_content)
    fixed_dxf.close()

    subprocess.run([oda_file_converter, output_path, output_path,
        'ACAD2013', 'DWG', '1', '1', filename + '.dxf'])
    subprocess.run(['rm', eps, dxf])


def main():
    args = [arg for arg in sys.argv] #[sys.argv.index("--") + 1:]]
    if scale_marker in args:
        scale_index = args.index(scale_marker) + 1 
        if ':' in args[scale_index] or '/' in args[scale_index]:
            scale = scale_re.search(args[scale_index])
            base_scale_factor = float(scale.group(1)) / float(scale.group(2))
        else: 
            base_scale_factor = float(args[scale_index])
        scale_factor = 1 / (base_scale_factor * 10)
        print(scale_factor)
    else:
        scale_factor = 1
    f = sys.argv[-1]
    path = Path(f)

    svg2dwg(path, scale_factor)

main()
