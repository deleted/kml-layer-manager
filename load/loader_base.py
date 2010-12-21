#!/usr/bin/env python

## __BEGIN_LICENSE__
## Copyright (C) 2006-2010 United States Government as represented by
## the Administrator of the National Aeronautics and Space Administration
## All Rights Reserved.
## __END_LICENSE__

import sys
import os
import math
import os.path
import logging
import urllib2
import optparse

for path in (
    '/Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/lib/fancy_urllib',
    '/home/ted/googleappengine/python/lib/fancy_urllib',
    '/home/ted/googleappengine/python',
    ):
    if os.path.exists(path):
        sys.path.insert(0,path)

sys.path.insert(0, '../client/')
import layers

from pds import Table

logging.basicConfig(filename='cmsclient.log', level=logging.DEBUG)
logging.getLogger('google.appengine.tools.appengine_rpc').setLevel(logging.DEBUG)
logger = logging.getLogger()


OUTPUT_path = 'out/'

CORNERS = tuple("corner%d"%(i+1,) for i in range(4))

if hasattr(__builtins__, "__dict__") and 'all' not in __builtins__.__dict__:
    # This is here for python2.4 compatability
    def all(iterator):
        for i in iterator:
            if not i: return False
        else:
            return True

class Observation(object):
    """
    Base class for PDS Observation metadata.
    The constructor takes:
        product: A dict of product label fields, usually yielded by iterating over a pds.Table object
        rectangular: Set this to False if the shape of the observation can't be described by four corner points
    """
    
    @property
    def url(self):
        """Override me in subclasses!"""
        raise NotImplementedError

    @property
    def schemafields(self):
        """ 
            A dict containing values to fill the associated KML Layerman schema of the form...
                fieldname: value
        """
        raise NotImplementedError

    def __init__(self, product, rectangular=True):
        self.__dict__ = product.__dict__
        if rectangular:
            assert all(hasattr(self, prop) for prop in ("%s_%s" % (corner, tude) for corner in CORNERS for tude in ("latitude","longitude")))
        self._latitude_properties = [prop for prop in ("%s_latitude" % corner for corner in CORNERS)]
        self._longitude_properties = [prop for prop in ("%s_longitude" % corner for corner in CORNERS)]
        self._fix_latitudes()
        self._fix_longitudes()
        if hasattr(self, 'product_id') and not hasattr(self,'observation_id'):
            self.observation_id = self.product_id

    @classmethod
    def normalize_corner_names(klass, property_dict):
        """ 
        Replace upper_left. upper_right style corner property names with corner1, corner2, etc
        This is nessecary because not all PDS labels observe consistent naming.
        """

        for tude in ('latitude','longitude'):
            for i, corner in enumerate(('upper_left','upper_right','lower_right','lower_left')):
                assert hasattr(property_dict, "%s_%s" % (corner, tude))
                setattr(property_dict, "corner%d_%s" % (i+1, tude), getattr(property_dict,"%s_%s" % (corner, tude)) )
                delattr(property_dict,"%s_%s" % (corner, tude))
                getattr(property_dict, "_%s_properties" % tude)[getattr(property_dict, "_%s_properties" % tude).index("%s_%s" % (corner, tude))] = "corner%d_%s" % (i+1, tude)
            getattr(property_dict, "_%s_properties" % tude).sort()
            assert all(hasattr(property_dict, attr) for attr in "corner%d_%s" % (ii+1, tude) for ii in range(4))
            assert getattr(property_dict,  "_%s_properties" % tude) == [ "corner%d_%s" % (ii+1, tude) for ii in range(4)]
            return property_dict

    @property
    def longitude(self):
        return self.corner4_longitude

    @property
    def latitude(self):
        return self.corner4_latitude

    @property
    def footprint(self):
        """
        Returns a list of coordinate pairs describing the obervation's footprint.
        This should be overridded by subclasses when the observation is non-rectanglar.
        """
        coords = []
        for i in (1,2,3,4,1):
            coords.append((
                getattr(self, 'corner%d_latitude' % i),
                getattr(self, 'corner%d_longitude' % i),
            ))
        return coords

    def get_geometries(self):
        """
        Return a **list** of geometry dicts, in the format accepted by the layermanager.
        (If you return a tuple, layermanager_client will cry)
        May be overridden by subclasses.
        """
        geometries = [
            {'type': 'Point', 'fields': {'location': (self.latitude, self.longitude)}},
            {'type':'Polygon', 'fields':{'outer_points': self.footprint}},
        ]
        return geometries
    

    def _fix_latitudes(self):
        for property in self._latitude_properties:
            value = getattr(self, property)
            if type(value) not in (int, float): raise TypeError
            if value > 180: raise ValueError # malformed value.  This observation should be skipped.
            
    def _fix_longitudes(self):
        for property in self._longitude_properties:
            value = getattr(self, property)
            if type(value) not in (int, float): raise TypeError
            if value > 360 or value < 0: raise ValueError # malformed value.  This observation should be skipped.
            if value > 180:
                value -= 360
                setattr(self, property, value)

class LayerLoader(object):
    world = 'mars'
    observation_class = Observation
    layer_options = {} # Any options stored here will be based as params on layer creation
   
    @property
    def layername(self):
        """ A String. """
        raise NotImplementedError

    @property
    def schema(self):
        """ 
        A dict with these members:
            name: A String
            fields: A sequence of dicts with these members:
                name: A String
                type: A String
        """
        raise NotImplementedError

    @property
    def template(self):
        """
        A dict with these members:
            name: A String
            text: A string, in django template format, which may reference the fields in the schema
        """
        raise NotImplementedError

    @property
    def style(self):
        """
        A sequence of dicts where keys are style properties and values are the corresponding values.
        """
        raise NotImplementedError


    def __init__(self, layername=None, metadata_path=None, label='CUMINDEX.LBL', table='CUMINDEX.TAB'):
        if layername:
            self.layername = layername
        if metadata_path:
            self.metadata_path = metadata_path
        assert hasattr(self, 'layername')
        assert hasattr(self, 'metadata_path')
        self.layer_id = None
        self.labelfile = os.path.join(self.metadata_path, label)
        self.tablefile = os.path.join(self.metadata_path, table)
        self.cms = layers.get_default_client()
        

    def generate_observations(self, max_observations=None):
        i = 0
        for row in Table(self.labelfile, self.tablefile):
            try:
                import pdb; pdb.set_trace()
                obs = self.observation_class(row)
            except ValueError, TypeError:
                # TODO: Log Me
                continue # skip records with problematic coordinates
            yield obs
            i += 1
            if max_observations > 0 and i >= max_observations:
                break

    def delete_existing_layers(self):
        name = self.layername
        cms = self.cms
        layer_ids = cms.List('layer')
        i = 0
        for lid in layer_ids:
            layer = cms.Query('layer', lid, lid, nocontents='true')
            if layer['name'] == name:
                cms.Delete('layer',lid)
                i += 1
        if i:
            print "Deleted %d existing layers." % i

    ####
    #  METHODS THAT APPLY TO RESUME MODE ONLY
    #
    def _get_first_layer(self):
        cms = self.cms
        name = self.layername
        print "Fetching existing layer %s..." % name,
        layer_ids = cms.List('layer')
        i = 0
        for lid in layer_ids:
            layer = cms.Query('layer', lid, lid, nocontents='true')
            if layer['name'] == name:
                print "Done."
                layer['id'] = lid
                #return layer
                return layers.lmc.Layer(cms, lid)
        else:
            raise Exception('Layer "%s" not found.' % name)

    def _get_schema_and_template(self):
        # Assume for now there's only one schema and one template per layer
        cms = self.cms
        print "Fetching schema...",
        schema_id = cms.List('schema', self.layer_id)[0]
        print "Done."
        print "Fetching template...",
        template_id = cms.List('template', self.layer_id, schema_id=schema_id)[0]
        print "Done."
        return (schema_id, template_id)

    def get_already_loaded_set(self):
        print "Loading successful uploads...",
        already_loaded = set()
        successfilename = "successful_uploads_%d.txt" % self.layer_id
        #with open(successfilename) as successfile:
        successfile = open(successfilename)
        for obsid in successfile:
            already_loaded.add(obsid.strip())
        successfile.close()
        print "Done. (%d observations already loaded)" % len(already_loaded)
        return already_loaded

    def resume_upload(self):
        cms = self.cms
        layername = self.layername
        layer = self._get_first_layer()
        self.layer_id = layer.id
        (schema_id, template_id) = self._get_schema_and_template()
        exclude_set = self._get_already_loaded_set()
        upload_nac_entities(cms, layer, schema_id, template_id, exclude=exclude_set)
    
#
# END RESUME MODE METHODS
####

    def generate_entities(self, style_id, schema_id, template_id, exclude=[], max_observations=None):
        for obs in self.generate_observations(max_observations=max_observations):
            observation_id = obs.observation_id
            if observation_id not in exclude:
                geometries = obs.get_geometries()
                schemafields = obs.schemafields
                yield dict(
                    type = 'entity',
                    name = observation_id,
                    style = style_id,
                    geometries = geometries,
                    schema = schema_id,
                    template = template_id,
                    **schemafields
                )
    

    def record_successful_entities(self, entities):
        logfile = open('successful_uploads_%d.txt' % self.layer_id,'a')
        for e in entities:
            logfile.write(e['name'] + "\n")
        logfile.close()

    def fetch_or_create_style(self):
        return layers.CmsObject.fetch_or_create('style', self.layer_id, **self.style)[0]


    def try_create_entities(self, entities, retries = 5):
        print "Uploading %d entities..." % len(entities),
        while retries > 0:
            try:
                self.cms.BatchCreateEntities(self.layer_id, entities)
                self.record_successful_entities(entities)
                print "Done."
                return True
            except urllib2.HTTPError, e:
                print "HTTP Error %d: %s" % (e.code, e.read())
                retries -= 1
        raise Exception("Too many retries.  Giving up.")

    def upload_entities(self, batchsize=200, exclude=[], max_observations=None):
        entities = []
        for entity in self.generate_entities(self.style_id, self.schema_id, self.template_id, exclude=exclude, max_observations=max_observations):
            entities.append(entity)   
            if len(entities) >= batchsize:
                self.try_create_entities(entities)
                entities = []
        else:
            self.try_create_entities(entities)
        print "Loaded %d observations."
        print "URL: ",self. layer.GetLayerKMLURL()

    def create_schema(self):
        (schema_id, template_id) = self.cms.CreateSchema(
            self.layer.id,
            self.schema['name'],
            self.schema['fields'], 
            [self.template],
        )
        return (schema_id, template_id)

    def load(self, max_observations=None, delete_existing=True):
        if delete_existing:
            self.delete_existing_layers()
        print "Creating Layer."
        self.layer = self.cms.Create('layer', name=self.layername, world=self.world, return_interface=True, **self.layer_options)
        self.layer_id = self.layer.id
        print "Creating Schema."
        self.schema_id, self.template_id = self.create_schema()
        print "Synching Style"
        self.style_id = self.fetch_or_create_style().id
        print "Loading Observations."
        sys.stdout.flush()
        self.upload_entities(max_observations=max_observations)
        print "Done."


def dispatch_cmd(context, argv):
    '''A helper for building command-line tools.'''
    commands = {}
    for name, value in context.iteritems():
        if name.startswith('cmd_') and callable(value):
            commands[name[4:]] = value
    if len(argv) < 2 or argv[1] not in commands:
        if context['__doc__']:
            print context['__doc__'] + '\n'
        print 'Usage: ' + sys.argv[0] + ' <command>' + '\n'
        print 'Commands: '
        for command, func in commands.iteritems():
            print '  %s : %s' % (command, func.__doc__)
        sys.exit(1)
    commands[argv[1]](*argv[2:])
