## __BEGIN_LICENSE__
## Copyright (C) 2006-2010 United States Government as represented by
## the Administrator of the National Aeronautics and Space Administration
## All Rights Reserved.
## __END_LICENSE__

import layermanager_client as lmc
import inspect

_cms_client = None
def get_default_client():
    from config import cms_connection_options
    global _cms_client
    if not _cms_client:
        _cms_client = lmc.LayersManagerClient(*cms_connection_options)
    return _cms_client

class MissingPropertyError(Exception): pass

def class_for_kind(kind):
    result = None
    classes = [c for c in globals().values() if inspect.isclass(c)]
    for klass in classes:
        if issubclass(klass, CmsObject) and klass.kind == kind:
            if result is not None:
                raise Exception("More than one class matches kind '%s'" % kind)
            result = klass
    if not result:
        raise Exception("class not found for kind '%s'" % kind)
    return result

class CmsObject(object):
    """
    This is the base class for the object oriented interface to the Layers CMS.
    It manages the business of creating objects and managing properties.
    It will lazily load object propeties only when nessecary.
    To update objects, set the property values and call the save() method.
    """

    kind = None # Override this in subclasses

    @classmethod
    def fetch_or_create(klass, kind, layer_id=None, *args, **kwargs):
        """
        If records exist on the CMS server that match the given keywords, get_or_create()
        will return a list of all matching objects (as instances of the appropriate CmsObject subclass).

        Otherwise, it will create a new object, save it to the server, and return a single-element
        list containing the new object.
        """
        def stringify_keys(dictionary):
            return dict((str(k), v) for (k,v) in dictionary.items())

        cms = get_default_client()
        if kind == 'layer':
            kwargs['nocontents'] = True
            if layer_id:
                kwargs['id'] = layer_id
        else:
            assert layer_id is not None

        if 'id' in kwargs:
            # Query and return [] wrapped result
            return [cms.Query(kind, layer_id, kwargs['id'])]
        else:
            # List and iterate
            if kind == 'layer':
                ids = cms.List(kind, **kwargs)
            else:
                ids = cms.List(kind, layer_id, **kwargs)
            results = []
            for id in ids:
                if kind == 'layer':
                    layer_id = id
                properties = cms.Query(kind, layer_id, id)
                for k, v in kwargs.items():
                    if k != 'nocontents' and properties[k] != v:
                        continue
                else:
                    results.append(properties)
            if len(results) > 0:
                results = [class_for_kind(kind)(layer_id, **stringify_keys(props)) for props in results]
                return results
            else:
                # create!
                new_cms_obj = class_for_kind(kind)(layer_id, **kwargs)
                new_cms_obj.save()
                return [new_cms_obj]

    @classmethod
    def get_first_by_name(klass, name, layer_id=None, cms=get_default_client()):
        kind = klass.kind
        if not layer_id and kind != 'layer':
            raise Exception("layer id required")
        print "Fetching existing layer %s..." % name,
        ids = cms.List(kind)
        i = 0
        for item_id in ids:
            item = cms.Query(kind, item_id, layer_id, nocontents='true')
            if item['name'] == name:
                print "Done."
                return item_id
        else:
            raise Exception('%s "%s" not found.' % (kind, name))

    def __init__(self, layer_id=0, **kwargs):
        kind = self.kind
        self._property_names = lmc.KNOWN_CMS_ARGUMENTS[kind]
        self._required_properties = lmc.REQUIRED_CMS_ARGUMENTS[kind]
        self.cms = kwargs.get('cms', None) or get_default_client()
        self._kind = kind
        self.id = kwargs.get('id', None)
        self.layer_id = layer_id
        self._properties_loaded = False
        self._properties_updated = False
        self._properties = {}
        for k, v in kwargs.items():
            self.__setattr__(k, v)

    def _load_properties(self):
        assert not self.is_unsaved # This shouldn't be called on a new, unsaved object
        tmp_new_properties = self._properties
        properties = self.cms.Query(self._kind, self.layer_id, self.id)
        self._properties = dict((str(k), v) for k, v in properties.items()) # convert keys from unicode to string (so they can be kwargs)
        assert type(self._properties) == dict
        self._properties.update(tmp_new_properties)
        self._properties_loaded = True


    @property
    def is_unsaved(self):
        return not self.id

    def __getattr__(self, name):
        if name in self._property_names:
            if name not in self._properties and not self._properties_loaded:
                if self.is_unsaved: # New, unsaved object.  No properties to retrieve.
                    return None
                else:
                    self._load_properties()
            return self._properties[name]
        else:
            raise AttributeError("No property: %s" % name)

    def __setattr__(self, name, value):
        if name == '_property_names':
            self.__dict__[name] = value
        if name in self._property_names:
            self._properties[name] = value
            self._properties_updated = True
        else:
            self.__dict__[name] = value
 
    def save(self):
        for prop in self._required_properties:
            if prop not in self._properties or not self._properties[prop]:
                raise MissingPropertyError('%s object missing required property "%s".' % (self.__class__.__name__, prop))
        if self.is_unsaved:
            self.id = self.cms.Create(self._kind, self.layer_id, **self._properties)
        else:
            if not self._properties_updated:
                return None #nothing to save
            self.cms.Update(self._kind, self.layer_id, **self._properties)
        self._properties_updated = False
        return True

class Layer(CmsObject):
    # TODO: Add icon upload functionality... (call FetchAndUpload)
    
    kind = 'layer'

    def __init__(self, id=0, **kwargs):
        CmsObject.__init__(self, layer_id=id, **kwargs)

    def save(self):
        is_new_layer = self.is_unsaved
        CmsObject.save(self)
        if is_new_layer:
            self.layer_id = self.id # is this actually necessary? (yes)

class Entity(CmsObject):
    kind = 'entity'
    
    def save(self):
        self.properties = self.cms._StandardizeEntity(self.layer_id, self.properties)
        CmsObject.save(self)

class Schema(CmsObject):
    kind = 'schema'

class Field(CmsObject):
    kind = 'field'

class Style(CmsObject):
    kind = 'style'

class Link(CmsObject):
    kind = 'link'

class Region(CmsObject):
    kind = 'region'

class Folder(CmsObject):
    kind = 'folder'

def batch_create_entities(layer, entities, retries=1, cms=get_default_client()):
    assert type(layer) in (int, Layer)
    if isinstance(layer, Layer):
        layer_id = layer.id
    else:
        layer_id = layer
    return cms.BatchCreateEntities(layer_id, [e.properties for e in entities], retries=retries)
