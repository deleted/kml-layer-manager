import layermanager_client as lmc
from config import cms_connection_options

_cms_client = None
def get_default_client():
    global _cms_client
    if not _cms_client:
        _cms_client = lmc.LayersManagerClient(*cms_connection_options)
    return _cms_client

class CmsObject(object):
    """
    This is the base class for the object oriented interface to the Layers CMS.
    It manages the business of creating objects and managing properties.
    It will lazily load object propeties only when nessecary.
    To update objects, set the property values and call the save() method.
    """
    
    def __init__(self, kind, layer_id=0, **kwargs):
        self._property_names = lmc.KNOWN_CMS_ARGUMENTS[kind]
        self.cms = kwargs.get('cms', None) or get_default_client()
        self._kind = kind
        self.id = kwargs.get('id', None) or None
        self.layer_id = layer_id
        if not self.id:
           self.id = self.cms.Create(kind, self.layer_id, **kwargs)
        self._properties_loaded = False
        self._properties_updated = False
        self._properties = {}

    def _load_properties(self):
        tmp_new_properties = self._properties
        properties = self.cms.Query(self._kind, self.layer_id, self.id)
        self._properties = dict((str(k), v) for k, v in properties.items()) # convert keys from unicode to string (so they can be kwargs)
        assert type(self._properties) == dict
        self._properties.update(tmp_new_properties)
        self._properties_loaded = True


    def __getattr__(self, name):
        if name in self._property_names:
            if name not in self._properties and not self._properties_loaded:
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
        if not self._properties_updated:
            return None #nothing to save
        self.cms.Update(self._kind, self.layer_id, **self._properties)
        self._properties_updated = False
        return True

class Layer(CmsObject):
    def __init__(self, name, world='mars', id=0, *args, **kwargs):
        kwargs['name'] = name
        kwargs['world'] = world
        CmsObject.__init__(self, 'layer', id, **kwargs)
        if not id: self.layer_id = self.id  # set to the new layer_id if this is a newly created layer
        self.icon = kwargs.get('icon', None)
        #import pdb; pdb.set_trace()
        self._layer = lmc.Layer(self.cms, self.id, self.icon)
