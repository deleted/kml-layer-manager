## __BEGIN_LICENSE__
## Copyright (C) 2006-2010 United States Government as represented by
## the Administrator of the National Aeronautics and Space Administration
## All Rights Reserved.
## __END_LICENSE__

from datetime import date
import loader_base
from loader_base import Observation, LayerLoader

"""
This module is completely untested and probably won't work as written.
To load LROC data, use lroc.py instead.  It does logically the same thing.

This file was created to hold the LROC specific logic 
when I extracted the more general-purpose loading logic from lroc.py into loader_base.py
"""


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

def LrocNacLoader(LayerLoader):

    world = "moon"
    layername = "LROC NAC " + date.today().strftime("%Y-%m-%d")
    
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


