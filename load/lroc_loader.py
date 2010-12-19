#!/usr/bin/env python2.6
## __BEGIN_LICENSE__
## Copyright (C) 2006-2010 United States Government as represented by
## the Administrator of the National Aeronautics and Space Administration
## All Rights Reserved.
## __END_LICENSE__

import os
from datetime import date
import loader_base
from loader_base import Observation, LayerLoader

"""
This module is completely untested and probably won't work as written.
To load LROC data, use lroc.py instead.  It does logically the same thing.

This file was created to hold the LROC specific logic 
when I extracted the more general-purpose loading logic from lroc.py into loader_base.py
"""
METADATA_PATH = os.path.join(os.environ['HOME'],'data/lroc')


class LrocNacProduct(Observation):
    def __init__(self, tablerow):
       tablerow.__dict__ = Product.normalize_corner_names(tablerow.__dict__)
       Observation.__init__(self, tablerow)
       self.observation_id = self.product_id[:-2]

    @property
    def url(self):
        volspec = self.file_specification_name.strip().split('/')[0]
        return "http://wms.lroc.asu.edu/lroc/view_lroc/%s/%s" % (volspec, self.product_id)



class NACObservation(dict):
    ''' 
        Big old hack. 
        Manages two observations as one.
    '''
    def __getattr__(self, attr):
        if 'L' in self:
            return getattr(self['L'], attr)
        elif 'R' in self:
            return getattr(self['R'], attr)
        else:
            raise AttributeError("No frames exist in this NACObservation.")
    def frames(self):
        # return((self['L'], self['R']))
        l = self.get('L', None)
        r = self.get('R', None)
        return (l,r) 

    def get_geometries(self):
        geometries = []
        geometries.append({'type': 'Point', 'fields': {'location': (self.latitude, self.longitude)}})
        for frame in self.frames():
            if frame:
                geometries.append({'type':'Polygon', 'fields':{'outer_points': frame.footprint}})
        return geometries

    @property
    def schemafields(self):
        schemafields = {}
        for side in ('left','right'):
            if side[0].upper() in obs:
                schemafields["field_%s_url" % side] = obs[side[0].upper()].url
                schemafields["field_%s_product_id" % side] = obs[side[0].upper()].product_id
        return schemafields

class NACFootprintObservation(NACObservation):
    def get_geometries(self):
        geometries = []
        for frame in self.frames():
            if frame:
                geometries.append({'type':'Polygon', 'fields':{'outer_points': frame.footprint}})
        return geometries
 

class LrocNACLoader(LayerLoader):

    world = "moon"
    layername = "LROC NAC " + date.today().strftime("%Y-%m-%d")
    observation_class = NACFootprintObservation
    metadata_path = METADATA_PATH
    layer_options = {
        'division_lod_min': 512,
        'division_lod_min_fade': 128,
    }
    
    schema = {
        'name': 'nac_schema',
        'fields': (
            {'name': 'left_url', 'type':'string'},
            {'name': 'left_product_id', 'type':'string'},
            {'name': 'right_url', 'type':'string'},
            {'name': 'right_product_id', 'type':'string'},
        )
    }    

    template = {
        'name': 'nac_template',
        'text': """
        <table width="360" border="0" cellpadding="0" cellspacing="0">
        <tr><td>Left Frame</td><td><a href="{{ left_url }}">{{ left_product_id }}</a></td></tr>
        <tr><td>Right Frame</td><td><a href="{{ right_url }}">{{ right_product_id }}</a></td></tr>
        </table>
        """
    }
    
    style = {
        'name': 'lroc_footprint',
        'polygon_outline': True,
        'polygon_fill': False,
        'line_width': 1,
        'line_color': 'FFFFFFFF', 
    }

class NACFootprintLoader(LrocNACLoader):
    layername = "LROC NAC footprints" + date.today().strftime("%Y-%m-%d")
    schema = {"name": "Empty Schema", "fields": []}
    observation_class = NACFootprintObservation
    layer_options = {
        # Set to fade out just as the main footprint loader is fading in.
        'division_lod_min': 256,
        'division_lod_min_fade': 128,
        'division_lod_max': 512,
        'division_lod_max_fade': 128,
    }

def cmd_load_footprints():
    """Just load the footprints layer (no icons or balloons) for display at high zoomlevels."""
    loader = NACFootprintLoader(label="INDEX.LBL", table="INDEX.TAB")
    loader.load()

if __name__ == "__main__":
    import sys
    #loader_base.dispatch_cmd(globals(), sys.argv)
    if len(sys.argv) > 1:
        if callable(globals().get("cmd_"+sys.argv[1], None)):
            globals().get("cmd_"+sys.argv[1])(*sys.argv[2:])
        else:
            print "Command not found: ", sys.argv[1]
    else:
        print "Command Required"

