#!/usr/bin/env python3 
# -*- coding: utf-8 -*- 

# Versioning IMAGE DIFFing


# Copyright (c) 2020 Marco Ferrara

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
# - imagediff.sh (https://github.com/marzof/scripts)
# - git

import sys
import subprocess, shlex
import tempfile
from pathlib import Path

home = str(Path.home())
imagediff = home + "/softwares/scripts/imagediff.sh"
resolution_marker = '-r'
args = sys.argv[1:]
resolution = '72'
base_files = args[:]
if resolution_marker in args:
    r_index = args.index(resolution_marker)
    resolution = args[r_index + 1]
    base_files = args[2:]

git_show_cmd = shlex.split('git show')
git_rev_parse_cmd = shlex.split('git rev-parse')
git_ls_files_cmd = shlex.split('git ls-files')
referred = lambda x: x if ':' in x else 'HEAD:' + x

def get_instructions():
    ''' Get the instructions in case of wrong input '''
    print('\nAdd one or two file to get the diff\n')
    print('## Simple example:\n')
    print('# Get the differences between the 2 files\n')
    print('\tvimagediff A.pdf B.png\n')
    print('## Versioning (git) usage:\n')
    print('# Get the diffs between current A.pdf and the last committed ' + \
            'version (HEAD:A.pdf)\n')
    print('\tvimagediff A.pdf\n')
    print('# Get the diffs between current A.pdf and the version of 4 ' + \
            'commits before HEAD of master branch\n')
    print('\tvimagediff master~4:A.pdf\n')
    print('# Get the diffs between A.pdf currently on branch_alpha and ' + \
            'the last committed version of A.pdf\n')
    print('\tvimagediff branch_alpha:A.pdf HEAD:A.pdf\n')
    print('# Get the diffs between A.pdf of commit 26bd806 and the ' + \
            'version of two commit before HEAD\n')
    print('\tvimagediff 26bd806:A.pdf HEAD~2:A.pdf\n')

def main():

    files = []

    ## Wrong files number
    if not 0<len(base_files)<3:
        get_instructions()
        return

    ## Simple comparison between two files
    if len(base_files) == 2 and ':' not in ' '.join(base_files):
        files = base_files
        subprocess.run([imagediff] + files + [resolution])  
        return
        
    ## Versioning comparison
    path = [None, None]
    temp_file = [None, None]
    
    git_repo = subprocess.run(git_rev_parse_cmd, stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE)

    ## Not a git repo
    if git_repo.stderr:
        get_instructions()
        return

    ## Get versioned files and add to files
    for i, b_file in enumerate(base_files):
        colon_idx = b_file.find(':')
        path[i] = b_file[colon_idx+1:]
        
        temp_file[i] = tempfile.NamedTemporaryFile(delete=False)
        show = subprocess.run(git_show_cmd + [referred(b_file)], 
                stdout=temp_file[i])
        temp_file[i].close()
        files.append(temp_file[i].name)

    if not temp_file[1]:
        files.append(path[0])

    subprocess.run([imagediff] + files + [resolution])  

main()
