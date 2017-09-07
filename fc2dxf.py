#!/usr/bin/env python
#
# Copyright (c) 2017 Marco Ferrara

# Purpose:
# This script reads a SVG file created by FreeCAD and creates multiple DXF files
# according to lines style (visible, hidden, thick, thin...).
# To convert SVG into DXF it runs the script "svgToDxf.sh" (that runs pstoedit).
# svgToDxf.sh is a script by Will Winder that I forked and slightly changed to
# fulfil my needs: you can find it at https://github.com/marzof/svgToDxf
# To merge all the dxf files you need the QCAD's merge script (see at
# http://www.ribbonsoft.com/en/qcad-documentation/qcad-command-line-tools).
# You also need to get the mf.py module at
# https://github.com/marzof/scripts/blob/master/mf.py

######################################
# REMEMBER:
# The script needs to use the svgToDxf.sh and the QCAD's merge script file so,
# after you download them, you have to change their location (search the corresponding
# lines at the beginning of tha main function) according to the actual paths in your
# machine
######################################
 
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


import sys
import os
import re
import subprocess
import random
import mf



def main(f):
    ## Matches all g tags and splits entire document by matched parts
    g_re = re.compile('(<g.*?<\/g>)',re.DOTALL)
    split_svg = re.split(g_re,mf.content_of_file(f))

    filename = re.sub('\.svg$', '', f)
    ######################################################
    ## Change path according to svgToDxf.sh location and QCAD location
    svg2dxf_path = '/home/mf/softwares/svgToDxf/svgToDxf.sh'
    dxfmerge_path = '/home/mf/softwares/qcad-pro/merge' 
    ######################################################
    hash_code = random.getrandbits(128)

    path_suffix = lambda x: '_%032x' % hash_code if x else ''
    actual_case = 0

    ## Checks what to do if a folder with same name exists yet
    cases = {
            'n': {
                'label': 'create a new folder with a different name',
                'suffix': True,
                'actions': lambda: os.makedirs(filename + path_suffix(True))
            },
            'a': {
                'label': 'archive the existing folder and create a new one', 
                'suffix': False,
                'actions': lambda: (os.rename(filename, 'archived_' + filename +
                    path_suffix(True)), os.makedirs(filename))
                },
            'r': {
                'label': 'add content to the existing folder and replace files ' +
                    'with same name',
                'suffix': False,
                'actions': lambda: None
                },
            0: {
                'label': '',
                'suffix': None,
                'actions': lambda: None
                },
            }

    cases_input = reduce(lambda x,y: x + y, ['\n' + c + ' - ' + cases[c]['label']
        for c in cases if c != 0])

    if not os.path.exists(filename):
        os.makedirs(filename)
    else:
        print 'A folder named "' + filename + '" exists yet.\
                \nWhat do you like to do?',
        while actual_case not in cases or actual_case == 0:
            actual_case = raw_input(cases_input + '\n')

    path = filename + path_suffix(cases[actual_case]['suffix'])


    ## Creates a dict for every tag containing stroke color definition (key: col).
    ## Stroke-dasharray (key: dsh) and stroke-width (key: wdt) are optional
    rule = '(?= stroke="#?(?P<col>[\d\w]+))(?:.* stroke-dasharray="(?P<dsh>[\d\.,]+))?(?:.* stroke-width="(?P<wdt>[\d\.,]+))?'

    ## Catches everything
    test = lambda x: True

    ## Gets the matched dicts in chars and replaces dots and commas with "-" and "_"
    ## then returns the dicts split in char lists
    label_dict = lambda x: [m.groupdict() for m in re.compile(rule).finditer(x)]
    label_dict_chars = lambda x: [c.replace(',','-').replace('.','_')
            for c in str(label_dict(x))]

    ## Removes dict punctuation and create a label
    punctuation = '[]{}\': '
    label = lambda x: reduce(lambda y, z: y + z if z not in punctuation else y,
            label_dict_chars(x), '') if len(label_dict(x)) > 0 else ''

    ## Re-assembles the split svg to re-establish the correct order that
    ## recursion had inverted
    action = lambda x, y, z: [z[k].insert(0, x) for k in z if k == y or y == '']

    list_dict = mf.lists_from_list(split_svg, test, label, action)

    cases[actual_case]['actions']()

    ## Create the xml for dxf merging
    print "Create xml for merging of following dict:"
    print [d for d in list_dict.keys() if len(d) > 0]
    xml_opening = '<?xml version="1.0" encoding="UTF-8"?> \
            <merge xmlns="http://qcad.org/merge/elements/1.0/" unit="Millimeter">'
    xml_item = lambda x: '<item src="' + filename + '-' + x + \
            '.dxf"><insert></insert></item>'
    xml_close = '</merge>'
    xml_body = xml_opening + \
            ''.join([xml_item(d) for d in list_dict.keys() if len(d) > 0]) + xml_close
    xml_path = path + '/' + filename + '.xml'
    xml_file = open(xml_path, 'w')
    xml_file.write(xml_body)
    xml_file.close()

    ## Add a page-sized rectangle to the svg
    re_viewbox = re.compile('viewBox="([\d ]+)"')
    a_dict = list_dict[list(list_dict)[1]][0]
    viewbox = re_viewbox.findall(a_dict)[0].split()
    print "Page size is" + str(viewbox[2:])
    rect = '<rect style="stroke:#000000;stroke-width:1;fill:none" id="rect999999" \
            width="' + viewbox[2] + '" height="' + viewbox[3] + '" \
            x="' + viewbox[0] + '" y="' + viewbox[1] + '" /></svg>'

    ## For every dict create an SVG file uniquely named, convert it to DXF and delete it
    for k in list_dict:
        if k is not '' and 'colnone' not in k:
            filepath = path + '/' + filename + '-' + k + '.svg'
            print 'Exporting ' + filepath
            f = open(filepath, 'w')
            ## Last line is replaced by rect
            [f.write(x) for x in list_dict[k][:-1]]
            f.write(rect)
            f.close()
            subprocess.call([svg2dxf_path, filepath])
            os.remove(filepath)

    ## Merge all dxfs in one
    merging_parameters = '-f -o ' + filename + '.dxf ' + path + '/' + filename + '.xml'
    subprocess.call(dxfmerge_path + ' ' + merging_parameters, shell=True)
    #subprocess.call([dxfmerge_path, merging_parameters])


if len(sys.argv) == 2:
    main (sys.argv[1])
else:
    print 'Add just one file name to run the application'
