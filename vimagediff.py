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

imagediff = "~/softwares/scripts/imagediff.sh"
args = sys.argv[1:]

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
    if not 0<len(args)<3:
        get_instructions()
        return

    ## Simple comparison between two files
    if len(args) == 2 and ':' not in ' '.join(args):
        files = sys.argv[1:]
        subprocess.run([imagediff] + files) 
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
    for i, arg in enumerate(sys.argv[1:]):
        colon_idx = arg.find(':')
        path[i] = arg[colon_idx+1:]
        
        temp_file[i] = tempfile.NamedTemporaryFile(delete=False)
        show = subprocess.run(git_show_cmd + [referred(arg)], 
                stdout=temp_file[i])
        temp_file[i].close()
        files.append(temp_file[i].name)

    if not temp_file[1]:
        files.append(path[0])

    subprocess.run([imagediff] + files) 

main()
