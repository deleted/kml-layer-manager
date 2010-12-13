#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""An client interface to the KML Layer Manager content management system."""

import base64
import mimetypes
import os
import re
import StringIO
import urllib
import urllib2
import urlparse
import warnings
import zipfile

# Try to find a JSON library. Any JSON library.
try:
  import json
except ImportError:
  import simplejson as json
if hasattr(json, 'read') and not hasattr(json, 'loads'):
  json.loads = json.read
  json.dumps = json.write

#python is soooo broken on byss...
import socket
if socket.gethostname().find("byss") == 0:
    import imp
    google = imp.load_module("google", *imp.find_module("google", ["/home/escharff/local/python"]))
from google.appengine.tools import appengine_rpc


KNOWN_CMS_ARGUMENTS = {
    'layer': [
        'name', 'description', 'custom_kml', 'icon', 'world', 'item_type',
        'dynamic_balloons', 'auto_managed', 'division_size', 'division_lod_min',
        'division_lod_min_fade', 'division_lod_max', 'division_lod_max_fade',
        # Note: "return_interface" is used internally and not sent to the CMS.
        'uncacheable', 'return_interface'
    ], 'entity': [
        'entity_id', 'name', 'snippet', 'view_latitude', 'view_longitude',
        'view_altitude', 'view_heading', 'view_tilt', 'view_roll', 'view_range',
        'view_is_camera', 'region', 'folder', 'folder_index', 'style', 'schema',
        # Note: "geometry" is replaced by "geometries" in _StandardizeEntity().
        'template', 'geometry', 'geometries', 'priority',
        re.compile(r'field_.*')
    ], 'folder': [
        'folder_id', 'name', 'icon', 'region', 'folder', 'folder_index',
        'description', 'item_type', 'custom_kml'
    ], 'link': [
        'link_id', 'name', 'icon', 'region', 'folder', 'url', 'folder_index',
        'description', 'item_type', 'custom_kml'
    ], 'permission': [
        re.compile(r'.+@.+_(access|manage|entities|resources|styles|schemas)'),
        'users'
    ], 'region': [
        'region_id', 'name', 'north', 'south', 'west', 'east', 'min_altitude',
        'max_altitude', 'altitude_mode', 'lod_min', 'lod_max', 'lod_fade_min',
        'lod_fade_max'
    ], 'schema': [
        # Note: "template", "templates" and "fields" are handled in Create().
        'schema_id', 'name', 'template', 'templates', 'fields'
    ], 'template': [
        'schema_id', 'template_id', 'name', 'text'
    ], 'field': [
        'schema_id', 'field_id', 'name', 'tip', 'type'
    ], 'style': [
        'style_id', 'name', 'has_highlight', 'icon', 'icon_color', 'icon_scale',
        'icon_heading', 'label_color', 'label_scale', 'balloon_color',
        'text_color', 'line_color', 'line_width', 'polygon_color',
        'polygon_fill', 'polygon_outline', 'highlight_icon',
        'highlight_icon_color', 'highlight_icon_scale',
        'highlight_icon_heading', 'highlight_label_color',
        'highlight_label_scale', 'highlight_balloon_color',
        'highlight_text_color', 'highlight_line_color', 'highlight_line_width',
        'highlight_polygon_color', 'highlight_polygon_fill',
        'highlight_polygon_outline'
    ], 'resource': [
        'type', 'filename', 'url', 'file'
    ], 'baker': []
}

REQUIRED_CMS_ARGUMENTS = {
    'layer': ['name','world'],
    'permission': [],
    'entity': [],
    'link': [],
    'style': [],
    'resource': [],
    'region': [],
    'field': [],
    'template': [],
    'folder': [],
    'baker': [],
    'schema': []
}

ICON_ARGUMENTS = {
    'layer': ['icon'],
    'folder': ['icon'],
    'link': ['icon'],
    'style': ['icon', 'highlight_icon']
}
MAX_RESOURCES_PER_REQUEST = 100


# pylint: disable-msg=C6113
# Lint, stop being dumb while parsing args from the docstring, please.
def GetKMLResource(url):
  """Gets a resource from a URL, resolving paths pointing inside a KMZ.

  Args:
    url: A URL, which may point inside a KMZ archive, such as in the case of:
        http://foo.com/bar/baz.kmz/icons/abc.png. Two corner cases:
        1. If there's a query string in a URL pointing inside a KMZ, it is
           ignored.
        2. URLs that point to the KMZ file itself, such as
           http://foo.com/bar/baz.kmz are fetched and returned directly, without
           being unzipped.

  Returns:
    The raw contents of the file at that URL, extracted if necessary.

  Raises:
    IOError: If an archive is fetched but does not contain the specified file.
  """
  (scheme, host, path, _, _) = urlparse.urlsplit(url)
  if '.kmz/' in path:
    kmz_path, inner_path = path.split('.kmz/', 1)
    kmz_path += '.kmz'
    kmz_url = urlparse.urlunsplit((scheme, host, kmz_path, None, None))
    kmz_data = urllib2.urlopen(kmz_url).read()
    kmz_file = StringIO.StringIO(kmz_data)
    zipper = zipfile.ZipFile(kmz_file)
    if inner_path in zipper.namelist():
      return zipper.read(inner_path)
    else:
      raise IOError('Path not found inside the archive.')
  else:
    return urllib2.urlopen(url).read()


class ManagerError(RuntimeError):
  """Indicates that an invalid action was requested from the CMS."""
  pass


# pylint: disable-msg=C6409
# Using underscore-prefixed argument names for methods that need to receive
# arbitrary keyword arguments to avoid aliasing.
# TODO(maxus): Rename this once we settle on a final external name for the CMS.
# TODO(maxus): Avoid duplicate resource creation when auto-detecting resources.
class LayersManagerClient(object):
  """An interface to access the Layers CMS."""

  def __init__(self, host, username, password, secure=False, save_cookie=False):
    """Initializes an authenticated connection to the CMS."""
    self.host = host
    self.rpc = appengine_rpc.HttpRpcServer(
        host=host, auth_function=lambda: (username, password), secure=secure,
        source='Layers CMS RPC', user_agent=None, save_cookies=save_cookie)
    self.layers_created = []
    self.last_request = None
    self._upload_url = None

  def Get(self, path, **get_args):
    """Sends a GET request to the CMS."""
    self.last_request = ('GET', path, get_args)
    try:
      return self.rpc.Send(path, None, **self._EncodeDict(get_args))
    except urllib2.HTTPError, e:
      if 400 <= e.code < 500:
        raise ManagerError('HTTP %d: %s' % (e.code, e.read()))
      elif not 200 <= e.code < 300:
        raise

  def Post(self, path, **post_args):
    """Sends a POST request to the CMS."""
    self.last_request = ('POST', path, post_args)
    sieved_post_args = {}
    for name, value in post_args.iteritems():
      if value is False:
        sieved_post_args[name] = ''
      elif value is not None:
        sieved_post_args[name] = value
    sieved_post_args = self._EncodeDict(sieved_post_args)
    try:
      return self.rpc.Send(path, urllib.urlencode(sieved_post_args),
                           content_type='application/x-www-form-urlencoded')
    except urllib2.HTTPError, e:
      if 400 <= e.code < 500:
        raise ManagerError('HTTP %d: %s' % (e.code, e.read()))
      elif not 200 <= e.code < 300:
        raise

  def Create(self, _type, _layer_id=0, **args):
    """Creates an item in the CMS and returns its ID."""
    self._VerifyTypeAndArgs(_type, args)
    if _type == 'resource':
      result = self.CreateResource(_layer_id,
                                   args['type'],
                                   args['filename'],
                                   args.get('url'),
                                   args.get('file'))
    elif _type == 'entity':
      result = self.CreateEntity(_layer_id, **args)
    elif _type == 'layer':
      result = self.CreateLayer(**args)
    elif _type == 'schema':
      fields = args.get('fields') or ()
      templates = args.get('templates') or ()
      if not templates and args.get('template'):
        templates = [args.get('template')]
      result = self.CreateSchema(_layer_id, args.get('name'), fields, templates)
    else:
      self._FindAndCreateIcons(_type, _layer_id, args)
      result = self.Post('/%s-create/%d' % (_type, int(_layer_id)), **args)
    return result

  def Update(self, _type, _layer_id, **args):
    """Updates an item in the CMS."""
    self._VerifyTypeAndArgs(_type, args)
    self._FindAndCreateIcons(_type, _layer_id, args)
    return self.Post('/%s-update/%d' % (_type, int(_layer_id)), **args)

  def Delete(self, _type, _layer_id, **post_args):
    """Deletes an item from the CMS."""
    self._VerifyTypeAndArgs(_type, post_args)
    return self.Post('/%s-delete/%d' % (_type, int(_layer_id)), **post_args)

  def Query(self, _type, _layer_id=0, _object_id=0, **extra_args):
    """Retrieves a representation of an item from the CMS."""
    self._VerifyTypeAndArgs(_type)
    result = self.Get('/%s-raw/%d' % (_type, int(_layer_id)),
                      id=_object_id, **extra_args)
    if _type == 'kml':
      return result
    else:
      return json.loads(result)

  def List(self, _type, _layer_id=0, **extra_args):
    """Lists the IDs of all items of a particular type in a layer."""
    self._VerifyTypeAndArgs(_type)
    result = self.Get('/%s-list/%d' % (_type, int(_layer_id)), **extra_args)
    return json.loads(result)

  def UndoLayers(self):
    """Delete any layers created using this instance. Useful for cleaning up."""
    for layer_id in self.layers_created:
      self.Delete('layer', layer_id)

  def GetLayerKMLURL(self, layer_id):
    """Constructs the URL of the (root) KML of a layer."""
    return 'http://%s/serve/%d/root.kml' % (self.host, int(layer_id))

  def GetAllLayerKMLURLs(self, layer_id):
    """Fetches a list of all KMLs generated for a layer."""
    return self.Get('/kml-list/%d' % int(layer_id)).strip().split('\n')

  def GetResourceURL(self, resource_id):
    """Constructs the absolute URL of a specified resource."""
    return 'http://%s/serve/0/r%d' % (self.host, int(resource_id))

  def GetRelativeResourceURL(self, resource_id, filename):
    """Constructs the relative URL of a specified resource."""
    # NOTE: This logic should be kept in sync with Resource.GetURL() in
    # model.py in the server.
    extension = re.search(r'.+\.(\w+)$', os.path.basename(filename))
    return 'r%s.%s' % (resource_id, extension.group(1))

  def CreateLayer(self, return_interface=False, **layer):
    """Creates a layer and takes care of creating an icon resource if needed.

    If an icon argument is specified as a URL or file path, it is read/fetched
    and created as a resource belonging to the layer then assigned to the layer.

    Args:
      return_interface: Whether to return a Layer object instead of a layer id.

    Returns:
      If return_interface is specified, an object that wraps the CMS API by
      automatically specifying the layer ID. Otherwise the ID of the new layer.
    """
    icon_id = None
    if 'icon' in layer:
      icon = layer['icon']
      del layer['icon']
      layer_id = self.Post('/layer-create/0', **layer)
      icon_id = self.FetchAndUpload(layer_id, icon, 'icon')
      self.Update('layer', layer_id, icon=icon_id)
    else:
      layer_id = self.Post('/layer-create/0', **layer)

    self.layers_created.append(layer_id)
    if return_interface:
      return Layer(self, layer_id, icon_id)
    else:
      return layer_id

  def CreateEntity(self, _layer_id, **entity):
    """Creates an entity, taking care of its geometries and their resources."""
    entity = self._StandardizeEntity(_layer_id, entity)
    return self.Post('/entity-create/%d' % int(_layer_id), **entity)

  def CreateSchema(self, layer_id, name, fields, templates):
    """Creates a schema together with its fields and templates.

    Args:
      layer_id: The layer that will contain the new schema.
      name: The name of the schema.
      fields: A list of field dictionaries, each having a name, a type and
          optionally a tip.
      templates: A list of template dictionaries, each having a name and a text.

    Returns:
      A 2-tuple, whose first entry is the schema ID, and whose second entry
      depends on the number of templates passed. If no templates where passed,
      it is None. If only one template was passed, it is the ID of that
      template. If multiple templates were passed, it is a list of their IDs.
    """
    schema_id = int(self.Post('/schema-create/%d' % int(layer_id), name=name))

    for field in fields:
      self.Create('field', layer_id, schema_id=schema_id, name=field['name'],
                  type=field['type'], tip=field.get('tip', ''))

    template_ids = []
    for template in templates:
      template_id = self.Create('template', layer_id, schema_id=schema_id,
                                name=template['name'], text=template['text'])
      template_ids.append(int(template_id))

    if not template_ids:
      return schema_id, None
    elif len(template_ids) == 1:
      return schema_id, template_ids[0]
    else:
      return schema_id, template_ids

  def CreateResource(self, layer_id, filetype, filename, url=None, data=None):
    """Creates a resource in the CMS and returns its ID.

    Args:
      layer_id: The ID of the layer which will contain the new resource.
      filetype: The type of the resource. Must be one of "icon", "image",
          "model" or "model_in_kmz".
      filename: The filename of the resource to upload.
      url: A URL that points to the resource data. Either this or data must be
          specified.
      data: The raw data contents of the resource. Either this or URL must be
          specified.

    Returns:
      The ID of the created resource.

    Raises:
      ManagerError: If neither or both data and url are specified.
    """
    if url and not data:
      upload_url = '/resource-create/%d' % int(layer_id)
      content_type = 'application/x-www-form-urlencoded'
      args = {'type': filetype, 'filename': filename, 'url': url}
      encoded_args = urllib.urlencode(self._EncodeDict(args))
    elif data and not url:
      upload_url = self._GetUploadURL(layer_id)[0]
      args = {'type': filetype, 'filename': filename}
      file_dict = {'file': (filename, data)}
      content_type, encoded_args = self._MultiPartEncode(args, file_dict)
    else:
      raise ManagerError('Must supply either data or URL to create a resource.')

    self.last_request = ('POST', upload_url, encoded_args)
    try:
      self.rpc.Send(upload_url, encoded_args, content_type=content_type)
    except urllib2.HTTPError, e:
      return self._FollowResourceRedirect(layer_id, e.code,
                                          e.headers.get('Location'))

  def BatchCreateResources(self, layer_id, resources):
    """Creates a group of resources in the CMS in a single batch request."""
    # TODO(maxus): Implement auto-retrying/continuation on timeout.
    if len(resources) > MAX_RESOURCES_PER_REQUEST:
      extra_resources = resources[MAX_RESOURCES_PER_REQUEST:]
      resources = resources[:MAX_RESOURCES_PER_REQUEST]
    else:
      extra_resources = None

    fields = {}
    files = {}

    for index, resource in enumerate(resources):
      fields['filename%d' % index] = resource['filename']
      fields['type%d' % index] = resource['type']
      data = resource.get('file')
      url = resource.get('url')
      if url and not data:
        fields['url%d' % index] = resource['url']
      elif data and not url:
        files['file%d' % index] = (resource['filename'], data)
      else:
        raise ManagerError('Must supply either data or URL for each resource.')

    if files:
      upload_url = self._GetUploadURL(layer_id)[1]
      content_type, encoded_args = self._MultiPartEncode(fields, files)
    else:
      upload_url = '/resource-bulk/%d' % int(layer_id)
      content_type = 'application/x-www-form-urlencoded'
      encoded_args = urllib.urlencode(self._EncodeDict(fields))

    self.last_request = ('POST', upload_url, encoded_args)
    try:
      self.rpc.Send(upload_url, encoded_args, content_type=content_type)
    except urllib2.HTTPError, e:
      ids = self._FollowResourceRedirect(layer_id, e.code,
                                         e.headers.get('Location'))
      ids = [int(i) for i in ids.split(',')]
      if extra_resources:
        return ids + self.BatchCreateResources(layer_id, extra_resources)
      else:
        return ids

  def BatchCreateEntities(self, layer_id, entities, retries=1):
    """Creates a group of entities in the CMS in a single batch request."""
    for index, entity in enumerate(entities):
      self._VerifyTypeAndArgs('entity', entity)
      entities[index] = self._StandardizeEntity(layer_id, entity)
    encoded = json.dumps(entities)
    result = self.Post('/entity-bulk/%d' % int(layer_id), entities=encoded)
    ids, error = result.split('\n', 1)
    ids = [int(i) for i in filter(None, ids.split(','))]
    entities = entities[len(ids):]
    # TODO(maxus): Do something more reliable than simply checking for a
    # specific message.
    if error == 'Ran out of time.':
      return ids + self.BatchCreateEntities(layer_id, entities)
    elif error:
      if retries > 0:
        return ids + self.BatchCreateEntities(layer_id, entities, retries - 1)
      raise ManagerError(error)
    else:
      return ids

  def FetchAndUpload(self, layer_id, url_or_path, filetype, filename=None):
    """Fetches a file and uploads it to the CMS, returning its ID."""
    if os.path.exists(url_or_path):
      if not filename:
        filename = os.path.basename(url_or_path)
      content = open(url_or_path).read()
    else:
      if not filename:
        filename = os.path.basename(urlparse.urlsplit(url_or_path)[2])
      content = GetKMLResource(url_or_path)

    return self.CreateResource(layer_id, filetype, filename, data=content)

  def _FindAndCreateIcons(self, object_type, layer_id, args):
    """Scans the arguments for icon fields and creates resources as needed.

    Scans the arguments dictionary for any fields known to expect a resource ID
    of an icon and if the value is a local path or URL, uploads or links to it
    by creating a resource on the CMS. The value is then replaced by the
    resource ID.

    Args:
      The type of object being created or updated.
      layer_id: The ID of the layer to which the object belongs or will belong.
          Used when creating resources.
      args: A dictionary arguments to be sent to the CMS server. If any
          resources are created, this dictionary is updated with their IDs.

    Raises:
      ManagerError: When an icon is specified as something other than an ID, an
      existing local path or a URL.
    """
    if object_type in ICON_ARGUMENTS:
      for arg in args:
        if arg in ICON_ARGUMENTS[object_type]:
          value = args[arg]
          if isinstance(value, basestring) and not value.isdigit():
            if os.path.exists(value):
              args[arg] = self.FetchAndUpload(layer_id, value, 'icon')
            elif urlparse.urlparse(value)[1]:
              args[arg] = self.CreateResource(
                  layer_id, 'icon', os.path.basename(value), url=value)
            else:
              raise ManagerError('The %s field of %s is expected to be an ID, '
                                 'an existing path, or a URL. Found: %s' %
                                 (arg, object_type, value))

  def _FollowResourceRedirect(self, layer_id, status_code, location):
    """Follows the redirect generated by a blobstore request.

    Args:
      layer_id: The layer to which the blobstore request was made.
      status_code: The status code which the blobstore request returned.
      location: The location header supplied in the response to the blobstore
          request.

    Returns:
      The result line of the response received from following the redirect.

    Raises:
      ManagerError: If the redirect had an error line.
    """
    if 300 <= status_code < 400:
      (_, _, path, query_string, _) = urlparse.urlsplit(location)
      args = (arg.split('=', 1) for arg in query_string.split('&'))
      args = dict((i[0], urllib.unquote(i[1])) for i in args)
      response = self.Get(path, **args)
      status, result, error, single_url, bulk_url = response.split('\n')
      if status == '200':
        self._upload_url = (layer_id, single_url, bulk_url)
        return result
      else:
        raise ManagerError('Resource creation error: %s' % error)
    else:
      raise ManagerError('Unexpected HTTP Status: %d' % status_code)

  def _GetUploadURL(self, layer_id):
    """Gets a pair of URLs which can be used to create resource(s) in the CMS.

    Args:
      layer_id: The ID of the layer in which the resources will be created.

    Returns:
      A pair of URLs, the first to be used for single uploads and the second
      for bulk uploads.
    """
    if self._upload_url and self._upload_url[0] == layer_id:
      single_url, bulk_url = self._upload_url[1:]
      self._upload_url = None
    else:
      response = self.Get('/resource-raw/%d' % int(layer_id), error='dummy')
      single_url, bulk_url = response.split('\n')[3:]

    (_, _, single_path, query_string, _) = urlparse.urlsplit(single_url)
    if query_string:
      single_path += '?' + query_string
    (_, _, bulk_path, query_string, _) = urlparse.urlsplit(bulk_url)
    if query_string:
      bulk_path += '?' + query_string

    return single_path, bulk_path

  def _StandardizeEntity(self, layer_id, entity):
    """Converts an entity description into a standard POSTable format.

    Converts the geometry/geometries field of the entity description from any of
    the formats accepted by the client to the one format accepted by the server.
    This includes:
      * If a "geometry" field is used, it is put into a list and set as
        "geometries".
      * Geometries in the form ('someType', someFields) are converted into
        {'type': 'someType', 'fields': someFields}.
      * Overlay images and 3D models which are specified as local paths or URLs
        are converted to resources (local files are uploaded; URLs are linked).
      * If geometries are not already JSON-encoded, they are encoded after the
        other steps are applied.

    It is safe to pass an entity through this function multiple times.

    Args:
      layer_id: The layer to which the entity is belongs or will belong. Used to
          upload any resources if needed.
      entity: An entity description dictionary.

    Returns:
      The entity description dictionary, converted to a standard format.

    Raises:
      ManagerError: When an invalid value is used in a geometry resource field.
    """
    if 'geometries' not in entity:
      if 'geometry' in entity:
        if isinstance(entity.get('geometry'), basestring):
          entity['geometries'] = '[%s]' % entity['geometry']
        else:
          entity['geometries'] = [entity['geometry']]
        del entity['geometry']
      else:
        return entity

    if isinstance(entity.get('geometries'), basestring):
      entity['geometries'] = json.loads(entity['geometries'])

    geometries = entity['geometries']
    for index, geometry in enumerate(geometries):
      if not isinstance(geometry, dict):
        geometry = dict(zip(('type', 'fields'), geometry))

      if (geometry['type'] in ('GroundOverlay', 'PhotoOverlay') and
          'image' in geometry['fields']):
        resource_field = 'image'
        resource_type = 'image'
      elif geometry['type'] == 'Model' and 'model' in geometry['fields']:
        resource_field = 'model'
        resource = geometry['fields'][resource_field]
        if isinstance(resource, basestring) and resource.endswith('.kmz'):
          resource_type = 'model_in_kmz'
        else:
          resource_type = 'model'
      else:
        geometries[index] = geometry
        continue

      resource = geometry['fields'][resource_field]
      if isinstance(resource, basestring) and not resource.isdigit():
        if os.path.exists(resource):
          resource = self.FetchAndUpload(layer_id, resource, resource_type)
        elif urlparse.urlparse(resource)[1]:
          resource = self.CreateResource(
              layer_id, resource_type, os.path.basename(resource), url=resource)
        else:
          raise ManagerError('Resource in a geometry is expected to be an ID, '
                             'an existing path, or a URL. Found: %s', resource)

        geometry['fields'][resource_field] = resource

      geometries[index] = geometry

    entity['geometries'] = json.dumps(geometries)

    return entity

  @staticmethod
  def _EncodeDict(args):
    """Encodes the unicode keys and values of a dictionary in UTF8."""
    encoded = {}
    for key, value in args.iteritems():
      if isinstance(key, unicode): key = key.encode('utf8')
      if isinstance(value, unicode): value = value.encode('utf8')
      encoded[key] = value
    return encoded

  @staticmethod
  def _VerifyTypeAndArgs(object_type, args=()):
    """Warns the user if unknown arguments are passed."""
    if object_type not in KNOWN_CMS_ARGUMENTS:
      warnings.warn('Unknown object type: ' + object_type)
    else:
      for arg in args:
        if arg not in KNOWN_CMS_ARGUMENTS[object_type]:
          valid = False
          for pattern in KNOWN_CMS_ARGUMENTS[object_type]:
            if hasattr(pattern, 'match') and pattern.match(arg):
              valid = True
              break
          if not valid:
            warnings.warn('Unknown argument for %s: %s' % (object_type, arg))

  @staticmethod
  def _MultiPartEncode(fields, files):
    """Encodes the specified fields and files as a multi-part form data.

    Args:
      fields: A dictionary of field names to field values.
      files: A dictionary mapping the names of the form fields which expect
          uploaded files to tuples of file names and contents. Note that values
          must be raw strings.

    Returns:
      A tuple containing the content type (including boundary) and the encoded
      fields and files string.
    """

    def Any(args):
      for i in args:
        if i: return True
      return False

    boundary = ''
    while Any(boundary in i[1] for i in files.itervalues()):
      boundary = base64.b64encode(os.urandom(16))

    lines = []
    for name, value in fields.iteritems():
      lines.append('--' + boundary)
      lines.append('Content-Disposition: form-data; name="%s"' % name)
      lines.append('')
      lines.append(value)
    for name, file_details in files.iteritems():
      filename, filedata = file_details
      datatype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
      lines.append('--' + boundary)
      lines.append('Content-Disposition: form-data; name="%s"; filename="%s"' %
                   (name, filename))
      lines.append('Content-Type: %s' % datatype)
      lines.append('')
      lines.append(filedata)
    lines.append('--' + boundary + '--')

    return 'multipart/form-data; boundary=' + boundary, '\r\n'.join(lines)


class Layer(object):
  """A wrapper around LayersManagerClient for acting on a specific layer."""

  def __init__(self, cms, layer_id, icon_id=None):
    self.cms = cms
    self.id = int(layer_id)
    self.icon_id = icon_id

  def Create(self, _type, **args):
    return self.cms.Create(_type, self.id, **args)

  def Update(self, _type, **args):
    return self.cms.Update(_type, self.id, **args)

  def Delete(self, _type, **post_args):
    return self.cms.Delete(_type, self.id, **post_args)

  def Query(self, _type, _object_id=0, **extra_args):
    return self.cms.Query(_type, self.id, _object_id, **extra_args)

  def List(self, _type, **extra_args):
    return self.cms.List(_type, self.id, **extra_args)

  def GetLayerKMLURL(self):
    return self.cms.GetLayerKMLURL(self.id)

  def GetAllLayerKMLURLs(self):
    return self.cms.GetAllLayerKMLURLs(self.id)

  def GetResourceURL(self, resource_id):
    return self.cms.GetResourceURL(resource_id)

  def CreateEntity(self, **entity):
    return self.cms.CreateEntity(self.id, **entity)

  def CreateSchema(self, name, fields, templates):
    return self.cms.CreateSchema(self.id, name, fields, templates)

  def CreateResource(self, filetype, filename, url=None, data=None):
    return self.cms.CreateResource(self.id, filetype, filename, url, data)

  def BatchCreateResources(self, resources):
    return self.cms.BatchCreateResources(self.id, resources)

  def BatchCreateEntities(self, entities, retries=1):
    return self.cms.BatchCreateEntities(self.id, entities, retries)

  def FetchAndUpload(self, url_or_path, filetype, filename=None):
    return self.cms.FetchAndUpload(self.id, url_or_path, filetype, filename)
