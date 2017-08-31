#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Marco Ferrara

# Purpose:
# My personal module: just a collection of functions I use for my scripts

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

def content_of_file(file):
    ''' Return the content of file '''
    f = open(file, 'r')
    c = f.read()
    f.close()
    return c

def printf(x):
    ''' Print as function '''
    print x

def lists_from_list(lst, test, label, action, a = {}, verbose = False):
    ''' Filter a list lst according to test and return a
        dict of lists using label as key and action as rule'''
    if verbose:
        print 'before:', lst, a
    if len(lst) > 0:
        if test(lst[0]) and label(lst[0]) not in a:
            a[label(lst[0])] = []
        lists_from_list(lst[1:], test, label, action, a, verbose)
        if test(lst[0]):
            action(lst[0], label(lst[0]), a)
        if verbose:
            print 'after:', lst, a
        return a

def export(content, filename):
    ''' Export content to filename '''
    f = open(filename, 'w')
    f.write(content)
    f.close()
