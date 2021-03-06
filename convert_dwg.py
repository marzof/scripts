#!/usr/bin/env python3
# -*- coding: utf-8 -*- 

import ezdxf
import os, sys
import pathlib
import subprocess

args = sys.argv[1:]
paths = [pathlib.Path(d).absolute() for d in args]
ODA_FILE_CONVERTER = '/usr/bin/ODAFileConverter'

for path in paths:
    subprocess.run([ODA_FILE_CONVERTER, path, path, 'ACAD2010', 'DXF', '1', '1',
        '*.dwg'])
    for root, dirs, files in os.walk(path):
        for name in files:
            if name.endswith(".dxf"):
                dxf = root + os.sep + name
                print('Converting', dxf)
                dxf_file = ezdxf.readfile(dxf, 'utf-8')
                dxf_file.saveas(dxf)
    subprocess.run([ODA_FILE_CONVERTER, path, path, 'ACAD2010', 'DWG', '1', '1',
        '*.dxf'])
    for root, dirs, files in os.walk(path):
        for name in files:
            if name.endswith(".dxf"):
                dxf = root + os.sep + name
                print('Removing', dxf)
                os.remove(dxf)
