#!/usr/bin/env python

import os
import re
import csv

whitespace_re = re.compile(r'^\s*$')
simple_entry_re = re.compile(r'^\s*([A-Z_^]+)\s*=\s*([-A-Z_0-9.:]+)\s*$')
string_entry_re = re.compile(r'^\s*([A-Z_^]+)\s*=\s*("(.*))?$')
string_start_re = re.compile(r'^\s*"(.*)')
string_end_re = re.compile(r'^([^"]*)"\s*$')
end_re = re.compile(r'^END\s*$')
end_object_re = re.compile(r'^\s*END_OBJECT')

class Label(object):
    def _parse_string(self, source, first):
        if not first:
            first = source.readline()
        if not first:
            raise ValueError('Malformed PDS label: Unexpected end of file!')
        m = string_start_re.match(first)
        if not m:
            raise ValueError('Malformed PDS label: Expected string constant!')
        first = m.group(1)
        value = ""
        while True:
            if first:
                line = first
                first = None
            else:
                line = source.readline()
                if not line:
                    raise ValueError('Malformed PDS label: Unexpected end of file!')
            m = string_end_re.match(line)
            if m:
                value += m.group(1)
                return value
            else:
                value += line

    def __init__(self, source, endre=end_re, permissive=False):
        self._properties = {}
        self.objects = []
        while True:
            line = source.readline()
            if not line:
                raise ValueError('Malformed PDS label: Unexpected end of file!')
            if endre.match(line):
                return
            if whitespace_re.match(line):
                continue
            m = simple_entry_re.match(line)
            if m:
                if m.group(1) == 'OBJECT':
                    object = Label(source,end_object_re,permissive=permissive)
                    object.id = m.group(2)
                    self.objects.append(object)
                    continue
                self._properties[m.group(1)] = m.group(2)
                continue
            m = string_entry_re.match(line)
            if m:
                self._properties[m.group(1)]= self._parse_string(source,m.group(2))
                continue
            if not permissive:
                raise ValueError('Malformed PDS label: ' + line)

    def __getitem__(self,key):
        return self._properties[key]

    def keys(self):
        return self._properties.keys()
            
class Table(object):
    def __init__(self, labelfile, tablefile=None, permissive=False):
        lbl = Label(open(labelfile,'r'), permissive=permissive)
        if tablefile is None:
            carats = [key for key in lbl.keys() if key[0] == '^']
            tablefile = os.path.join( os.path.dirname(labelfile), lbl[carats[0]] )
        self.table = csv.reader( open( tablefile, 'r' ) )
        columns = lbl.objects[0].objects
        self._column_parsers = [self._column_parser(column) for column in columns]

    def _string_entry(self,name):
        return lambda val: (name, val.strip())

    def _integer_entry(self,name):
        def parser(val):
            try:
                return (name, int(val))
            except ValueError:
                return (name, val.strip())
        return parser

    def _real_entry(self,name):
        def parser(val):
            try:
                return (name, float(val))
            except ValueError:
                return (name, val.strip())
        return parser

    def _column_parser(self,column):
        type = column['DATA_TYPE']
        name = column['NAME'].lower()
        if type == 'ASCII_INTEGER':
            return self._integer_entry(name)
        if type == 'ASCII_REAL':
            return self._real_entry(name)
        return self._string_entry(name)

    class Row(object):
        def __init__(self,table,row):
            self.__dict__.update([parse(entry) for parse, entry in zip(table._column_parsers,row)])

    def __iter__(self):
        for row in self.table:
            yield Table.Row(self,row)
