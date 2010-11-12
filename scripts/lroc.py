#!/usr/bin/env python
import sys
import os
import math
import os.path
import logging
import urllib2
import optparse

sys.path.insert(0, '/home/ted/googleappengine/python')
sys.path.insert(0, '/home/ted/googleappengine/python/lib/fancy_urllib') # Because it's installed in a weird way.
sys.path.insert(0, '../client/')

import layers

from pds import Table

logging.basicConfig(filename='cmsclient.log', level=logging.DEBUG)
logging.getLogger('google.appengine.tools.appengine_rpc').setLevel(logging.DEBUG)
logger = logging.getLogger()


OUTPUT_path = 'out/'
METADATA_PATH = os.path.join(os.environ['HOME'],'data/lroc')


class Observation(object):
    def __init__(self, product):
        self.__dict__ = product.__dict__
        self._fix_latitudes()
        self._fix_longitudes()
        self.observation_id = self.product_id[:-2]
        # HACK: alias corner property names
        for i, corner in enumerate(('upper_left','upper_right','lower_right','lower_left')):
            for tude in ('latitude','longitude'):
                setattr(self, "corner%d_%s" % (i+1, tude), getattr(self,"%s_%s" % (corner, tude)) )
                delattr(self,"%s_%s" % (corner, tude))

    @property
    def longitude(self):
        return self.corner4_longitude

    @property
    def latitude(self):
        return self.corner4_latitude

    @property
    def footprint(self):
        coords = []
        for i in (1,2,3,4,1):
            coords.append((
                getattr(self, 'corner%d_latitude' % i),
                getattr(self, 'corner%d_longitude' % i),
            ))
        return coords
    
    @property
    def url(self):
        volspec = self.file_specification_name.strip().split('/')[0]
        return "http://wms.lroc.asu.edu/lroc/view_lroc/%s/%s" % (volspec, self.product_id)

    def _fix_latitudes(self):
        for property in (
            'center_latitude',
            'upper_left_latitude',
            'upper_right_latitude',
            'lower_right_latitude',
            'lower_left_latitude',
        ):
            value = getattr(self, property)
            if type(value) not in (int, float): raise TypeError
            if value > 180: raise ValueError # malformed value.  This observation should be skipped.
            
    def _fix_longitudes(self):
        for property in (
            'center_longitude',
            'upper_left_longitude',
            'upper_right_longitude',
            'lower_right_longitude',
            'lower_left_longitude',
        ):
            value = getattr(self, property)
            if type(value) not in (int, float): raise TypeError
            if value > 360: raise ValueError # malformed value.  This observation should be skipped.
            if value > 180:
                value -= 360
                setattr(self, property, value)
                
class NACObservation(dict):
    ''' Big old hack. '''
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


def generate_nac_observations(cumindex_dir=METADATA_PATH, max_observations=None):
    nac_observations = {}
    i = 0
    for row in Table(os.path.join(METADATA_PATH, 'CUMINDEX.LBL'), os.path.join(METADATA_PATH, 'CUMINDEX.TAB')):
        try:
            obs = Observation(row)
        except ValueError, TypeError:
            continue # skip records with problematic coordinates
        if obs.product_id[-2] in ('L','R'):
            obs_id = obs.product_id[:-2]
            if obs_id not in nac_observations:
                nac_observations[obs_id] = NACObservation()
            nac_observations[obs_id][obs.product_id[-2]] = obs
            if 'L' in nac_observations[obs_id] and 'R' in nac_observations[obs_id]:
                yield obs_id, nac_observations.pop(obs_id)
                i += 1
        else:
            # Assuming all other letters are WAC observations...
            #wac_observations[obs.product_id[:-1]] = obs
            pass
        if max_observations > 0 and i >= max_observations:
            break
    else:
        while len(nac_observations) > 0:
            if max_observations > 0 and i > max_observations: 
                break
            obs_id, obs = nac_observations.popitem()
            yield obs_id, obs
            i += 1

def delete_existing_layers(cms, name):
    layer_ids = cms.List('layer')
    i = 0
    for lid in layer_ids:
        layer = cms.Query('layer', lid, lid, nocontnets='true')
        if layer['name'] == name:
            cms.Delete('layer',lid)
            i += 1
    if i:
        print "Deleted %d existing layers." % i

def get_by_name(cms, kind, name, layer_id=None):
    if not layer and kind != 'layer':
        raise Exception("layer id required")
    print "Fetching existing layer %s..." % name,
    layer_ids = cms.List(kind)
    i = 0
    for id in layer_ids:
        layer = cms.Query(kind, id, layer_id, nocontents='true')
        if layer['name'] == name:
            print "Done."
            return layer_id
    else:
        raise Exception('Layer "%s" not found.' % name)

def get_first_layer(cms, name):
    print "Fetching existing layer %s..." % name,
    layer_ids = cms.List('layer')
    i = 0
    for lid in layer_ids:
        layer = cms.Query('layer', lid, lid, nocontents='true')
        if layer['name'] == name:
            print "Done."
            return lid
    else:
        raise Exception('Layer "%s" not found.' % name)

def get_schema_and_template(cms, layer_id):
    # Assume for now there's only one schema and one template per layer
    print "Fetching schema...",
    schema_id = cms.List('schema', layer_id)[0]
    print "Done."
    print "Fetching template...",
    template_id = cms.List('template', layer_id, schema_id=schema_id)[0]
    print "Done."
    return (schema_id, template_id)

def get_already_loaded_set():
    print "Loading successful uploads...",
    already_loaded = set()
    with open('successful_uploads.txt') as successfile:
        for obsid in successfile:
            already_loaded.add(obsid.strip())
    print "Done. (%d observations already loaded)" % len(already_loaded)
    return already_loaded

"""
def generate_nac_entities(nac_observations):
    for observation_id, obs in nac_observations.items():
"""
def generate_nac_entities(style, schema_id, template_id, exclude=[]):
    for observation_id, obs in generate_nac_observations():
        if observation_id not in exclude:
            geometries = []
            geometries.append({'type': 'Point', 'fields': {'location': (obs.latitude, obs.longitude)}})
            for frame in obs.frames():
                if frame:
                    geometries.append({'type':'Polygon', 'fields':{'outer_points': frame.footprint}})
            schemafields = {}
            for side in ('left','right'):
                if side[0].upper() in obs:
                    schemafields["field_%s_url" % side] = obs[side[0].upper()].url
                    schemafields["field_%s_product_id" % side] = obs[side[0].upper()].product_id
            yield dict(
                type = 'entity',
                name = observation_id,
                style = style,
                geometries = geometries,
                #geometry = geometries[0],
                schema = schema_id,
                template = template_id,
                **schemafields
            )
    

def record_successful_entities(entities):
    logfile = open('successful_uploads.txt','wa')
    for e in entities:
        logfile.write(e['name'] + "\n")
    logfile.close()

def lroc_style(layer_id):
    styleprops = {
        'name': 'lroc_footprint',
        'polygon_outline': True,
        'polygon_fill': False,
        'line_width': 1,
        'line_color': 'FFFFFFFF',
    }
    style = layers.CmsObject.fetch_or_create('style', layer_id, **styleprops)[0]
    return style


def try_create_entities(cms, layer_id, entities, retries = 3):
    print "Uploading %d entities..." % len(entities),
    while retries > 0:
        try:
            cms.BatchCreateEntities(layer_id, entities)
            record_successful_entities(entities)
            print "Done."
            return True
        except urllib2.HTTPError, e:
            print "HTTP Error %d: %s" % (e.code, e.read())
            retries -= 1
    raise Exception("Too many retries.  Giving up.")

def upload_nac_entities(cms, layer, schema_id, template_id, batchsize=200, exclude=[]):
    style = lroc_style()
    entities = []
    for entity in generate_nac_entities(style.id, schema_id, template_id, exclude=exclude):
        entities.append(entity)   
        ### TODO: bulk upload this list when it accumulates to a given size
        if len(entities) >= batchsize:
            success = False
            try_create_entities(cms, layer.id, entities)
            entities = []
    else:
        try_create_entities(layer.id, entities)
    print "Loaded %d observations."
    print "URL: ", layer.GetLayerKMLURL()

def create_nac_schema(cms, layer):
    template_text = """
    <table width="360" border="0" cellpadding="0" cellspacing="0">
    <tr><td>Left Frame</td><td><a href="{{ left_url }}">{{ left_product_id }}</a></td></tr>
    <tr><td>Right Frame</td><td><a href="{{ right_url }}">{{ right_product_id }}</a></td></tr>
    </table>
    """
    (schema_id, template_id) = cms.CreateSchema(
        layer.id,
        'nac_schema',
        [
            {'name': 'left_url', 'type':'string'},
            {'name': 'left_product_id', 'type':'string'},
            {'name': 'right_url', 'type':'string'},
            {'name': 'right_product_id', 'type':'string'},
        ],
        [
            {'name': 'nac_template', 'text': template_text},
        ],
    )
    return (schema_id, template_id)

def main():
    layername="LROC NAC"

    parser = optparse.OptionParser()
    parser.add_option('--resume', action='store_true', dest='resume', default=False)
    (options, args) = parser.parse_args()

    print "Getting connection...",
    cms = layers.get_default_client()
    print "Done."
    if options.resume:
        print "RESUME MODE"
        layer_id = get_first_layer(cms, layername)
        (schema_id, template_id) = get_schema_and_template(cms, layer_id)
        exclude_set = get_already_loaded_set()
        upload_nac_entities(cms, layer_id, schema_id, template_id, exclude=exclude_set)

    else:
        print "Creating layer."
        delete_existing_layers(cms, layername)
        layer = cms.Create('layer', name=layername, world='mars', return_interface=True)
        print "Creating Schema"
        (schema_id, template_id) = create_nac_schema(cms, layer)
        print "Loading observations."
        sys.stdout.flush()
        upload_nac_entities(cms, layer, schema_id, template_id)

if __name__ == '__main__':
    main()
