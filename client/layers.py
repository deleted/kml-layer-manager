import layermanager_client as lmc
from config import cms_connection_options

_cms_client = None
def get_default_client():
    global _cms_client
    if not _cms_client:
        _cms_client = lmc.LayersManagerClient(*cms_connection_options)
    return _cms_client

class MissingPropertyError(Exception): pass

class CmsObject(object):
    """
    This is the base class for the object oriented interface to the Layers CMS.
    It manages the business of creating objects and managing properties.
    It will lazily load object propeties only when nessecary.
    To update objects, set the property values and call the save() method.
    """
    
    def __init__(self, kind, layer_id=0, **kwargs):
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
        #elif name in self.__dict__:
        else:
            self.__dict__[name] = value
        #else:
        #    raise AttributeError("No property or attribute: %s" % name)
 
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
    def __init__(self, id=0, **kwargs):
        CmsObject.__init__(self, 'layer', id, **kwargs)
        #self.icon = kwargs.get('icon', None)
        #self._layer = lmc.Layer(self.cms, self.id, self.icon)

    def save(self):
        is_new_layer = self.is_unsaved
        CmsObject.save(self)
        if is_new_layer:
            self.layer_id = self.id # is this actually necessary?
