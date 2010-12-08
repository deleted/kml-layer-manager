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

"""The model definitions for data objects and their KML serializers."""


import datetime
import itertools
import operator
import os
import re
import time
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext.db import polymodel
from google.appengine.ext.webapp import template
from lib.geo import geomodel
import util


# The set of valid values for altitude mode.
#   clampToGround: The altitude is ignored, and all parts of the object are
#       positioned at ground altitude.
#   relativeToGround: The altitude of each port of the object is calculated
#       relative the altitude of the ground at that point.
#   absolute: The altitude is interpreted relative to sea level.
_ALTITUDE_MODES = ['clampToGround', 'relativeToGround', 'absolute']

# A cache for compiled KML templates. Safe to persist across requests, since
# it is generated from static files.
_kml_template_cache = {}


class KMLGenerationError(RuntimeError):
  """An exception thrown when an error occurs during KML generation."""
  pass


def _ValidateDjangoTemplate(template_text):
  """Validates the input text as a Django v96.0 template."""
  if not template_text: return
  try:
    template.register_template_library('template_functions.entities')
    template.Template(template_text)
  except template.django.template.TemplateSyntaxError, e:
    raise db.BadValueError('Invalid template syntax: %s' % e)


def _ValidateTilt(tilt_degrees):
  """Validates that the provided tilt value is between 0 and 90 degrees."""
  if tilt_degrees is not None and not 0 <= tilt_degrees <= 180:
    raise db.BadValueError('Tilt must be between 0 and 90 degrees.')


def _ValidateKMLColor(color):
  """Ensures that a given string is a valid KML color."""
  if color is not None and not re.match('^[\da-fA-F]{8}$', color):
    raise db.BadValueError('Invalid KML color; must be in the AABBGGRR format.')


def _RenderKMLTemplate(filename, args):
  """Renders the specified templates with custom KML filters auto-registered."""
  if filename not in _kml_template_cache:
    template.register_template_library('template_functions.kml')
    template_path = os.path.join('kml_templates', filename)
    _kml_template_cache[filename] = template.load(template_path)
  return _kml_template_cache[filename].render(template.Context(args))


def ForceIntoUnicode(string):
  """Converts a string to unicode (assuming UTF8) if it's not already."""
  if isinstance(string, unicode):
    return string
  else:
    return string.decode('utf8')


class AuthenticatedUser(db.Model):
  """A user allowed access to the application."""
  user = db.UserProperty(required=True)


class ContainerModelBase(db.Model):
  """A base class for containers. Only to reduce redundancy, so not a PolyModel.

  Should not be instantiated directly.

  Properties:
    name: The name of the container as it appears in the editor as well as in
        Google Earth.
    description: A description of the container to be displayed in a balloon
        in Google Earth. This is parsed as a Django template.
    icon: A reference to a resource that is used as the icon of this container
        in both the editor and Google Earth.
    custom_kml: An arbitrary KML string that is placed in the root element of
        the KML generated for the container.
    item_type: A choice controlling how the contents of the container are
        displayed in Google Earth's list view.
  """

  # The set of valid values for an item type.
  #   check: The visibility of the container's contents are controlled by the
  #       container's checkbox as well as their own.
  #   radioFolder: Only one of the folder's contents can be visible at a time.
  #   checkOffOnly: The contents can be hidden using the container's checkbox,
  #       but not shown except by their own checkbox.
  #   checkHideChildren: The container's contents are all shown or hidden by the
  #       container's checkbox, and do not appear in the list.
  CONTAINER_TYPES = {
      'check': 'Checkbox',
      'radioFolder': 'Radio Button',
      'checkOffOnly': 'Checkbox (Hide Only)',
      'checkHideChildren': 'Hidden'
  }

  name = db.StringProperty(required=True, indexed=False)
  description = db.TextProperty(validator=_ValidateDjangoTemplate)
  # NOTE: icon is a Resource reference, but we aren't specifying it as one to
  # avoid a circular dependency (since Resource references Layer).
  icon = db.ReferenceProperty()
  custom_kml = db.TextProperty()
  item_type = db.StringProperty(choices=CONTAINER_TYPES.keys(), indexed=False)

  def EvaluateDescription(self):
    """Evaluates Django tags in the container's description."""
    if self.description:
      template.register_template_library('template_functions.entities')
      if isinstance(self.description, unicode):
        encoded_text = self.description.encode('utf8')
      else:
        encoded_text = self.description
      args = {'container': self}
      evaluated = template.Template(encoded_text).render(template.Context(args))
      return ForceIntoUnicode(evaluated)


class Layer(ContainerModelBase):
  """A Datastore model for layer objects used as a container for entities.

  A Layer repesents a collection of entities that should be shown or hidden all
  at once and follow a similar theme. A Layer object contains a set of styles,
  schemas, entities, folders, links and images that are grouped together and can
  be automatically rendered as KML. Most contents of a layer are not defiend as
  part of the Layer model, but instead each component link to its parent layer
  in its model.

  Explicit Properties:
    world: The sphere to use when displaying this layer, e.g. Earth, Mars, Sky.
    busy: Whether this layer is currently busy, being either regionated or
        deleted. It is strongly suggested not to update the layer or any of its
        contents if this flag is set to True.
    uncacheable: If True, nothing in the layer is ever cached.
    compressed: Whether to serve KMZs instead of KMLs.
    dynamic_balloons: Whether to serve the entity balloon contents for this
        layer dynamically, instead of baking them into the KML.
    auto_managed: A flag indicating that this layer is managed automatically.
        This is used for huge layers to block access to manual editing forms.
    baked: Whether this layer has been baked (auto-regionated), Has no effect on
        non-auto-managed layers.
    division_size: A soft bound on the maximum number of entities in a single
        division. Leaf divisions may have up to 1.5 time this number. Has no
        effect on non-auto-managed layers.
    division_lod_min: The minimum number pixels that a region generated via
        auto-regionation has to take up on the screen to be activated. Has no
        effect on non-auto-managed layers.
    division_lod_min_fade: The distance over which the geometry fades, from
        fully opaque to fully transparent. Has no effect on non-auto-managed
        layers.
    division_lod_max: The maximum number pixels that a region generated via
        auto-regionation has to take up on the screen to be activated. Has no
        effect on non-auto-managed layers.
    division_lod_max_fade: The distance over which the geometry fades, from
        fully transparent to fully opaque. Has no effect on non-auto-managed
        layers.
    cached_kml: The cached KML representation of the layer. This should be
        reset to None whenever the layer is updated.
    timestamp: The last modified timestamp.

  Properties inherited from ContainerModelBase:
    name, description, icon, custom_kml, item_type: See the ContainerModelBase
    docstring for details.

  Auto-generated Properties:
    entity_set: The set of all entities belonging to this layer.
    folder_set: The set of all folders belonging to this layer.
    permission_set: The set of permissions governing this layer.
    schema_set: The set of all schemas belonging to this layer.
    style_set: The set of all styles belonging to this layer.
    link_set: The set of all links belonging to this layer.
    region_set: The set of all regions belonging to this layer.
    division_set: The set of all divisions belonging to this layer.
    resource_set:The set of all resources belonging to this layer.
  """

  WORLDS = ['earth', 'moon', 'mars', 'sky']

  world = db.StringProperty(choices=WORLDS, required=True)
  busy = db.BooleanProperty()
  uncacheable = db.BooleanProperty()
  compressed = db.BooleanProperty()
  dynamic_balloons = db.BooleanProperty()
  auto_managed = db.BooleanProperty()
  baked = db.BooleanProperty()
  division_size = db.IntegerProperty(indexed=False)
  division_lod_min = db.IntegerProperty(indexed=False)
  division_lod_min_fade = db.IntegerProperty(indexed=False)
  division_lod_max = db.IntegerProperty(indexed=False)
  division_lod_max_fade = db.IntegerProperty(indexed=False)
  cached_kml = db.TextProperty()
  timestamp = db.DateTimeProperty(auto_now=True)

  def GetResources(self, resource_type):
    """Gets a list of the layer's resources.

    Args:
      resource_type: The type of resource to return. One of Resource.TYPES.

    Returns:
      A query that will return Resource objects of the specified type belonging
      to this layer.

    Raises:
      ValueError: If an invalid type was specified.
    """
    if resource_type in Resource.TYPES:
      return self.resource_set.filter('type', resource_type)
    else:
      raise ValueError('Invalid resource type specified: %s' % resource_type)

  def IsPermitted(self, user, permission_type):
    """Returns whether the given user has the given permission for this layer.

    Args:
      user: A User object to check permissions for.
      permission_type: The type of the permission against which to check. One of
          the constants from the Permission.TYPES.

    Returns:
      A Boolean indicating whether the specified user has the specified
      permission on this layer.
    """
    acl = self.permission_set.filter('user', user)
    permission = acl.filter('type', permission_type)
    return permission.get() is not None

  def SafeDelete(self):
    """Deletes the layer with its permissions in a transaction."""

    def Delete():
      for permission in self.permission_set.ancestor(self):
        permission.delete()
      self.delete()
    db.run_in_transaction(Delete)

  def GenerateKML(self, cache=None):
    """Serializes the layer as a KML document.

    Generates a single KML file that includes everything in the layer: styles,
    entities (structured into folders) and custom KML snippets.

    Args:
      cache: An optional collections.defaultdict to use as a cache.

    Returns:
      A string representing the layer as a KML document, including the XML
      declaration and the all-enclosing <kml> tags. If the layer is auto
      managed, some of the layer's contents will be contained in other linked
      KML files.

    Raises:
      KMLGenerationError: If the layer is auto-managed but not baked yet.
    """
    if not self.cached_kml or self.uncacheable:
      self.cached_kml = self._DoGenerateKML(cache)
      if not self.uncacheable: self.put()
    return self.cached_kml

  def _DoGenerateKML(self, cache):
    """Implements the actual KML generation as specified by GenerateKML()."""
    if self.auto_managed:
      if self.baked:
        root_division = self.division_set.filter('parent_division', None).get()
        items = Entity.get_by_id(root_division.entities)
        items += list(root_division.division_set)
        items += list(self.link_set)
        # Don't forget entities that have not been assigned to a division yet.
        # This happens when new entities where added since the layer was last
        # baked.
        items += self.entity_set.filter('baked', None)
        # Folders are ignored in baked layers to avoid duplicating entities.
      else:
        raise KMLGenerationError('Cannot generate unbaked auto-managed layer.')
    else:
      items = self.GetSortedContents()

    items_kml = []
    for item in items:
      if isinstance(item, Division):
        item_kml = item.GenerateLinkKML()
      else:
        item_kml = item.GenerateKML(cache)
      items_kml.append(item_kml)
    styles = [i.GenerateKML(cache) for i in self.style_set]

    args = {
        'layer': self,
        'contents': items_kml,
        'styles': styles,
        'description': self.EvaluateDescription()
    }
    return ForceIntoUnicode(_RenderKMLTemplate('layer.kml', args))

  def ClearCache(self):
    """Clears the cached KML representation of this layer."""
    # Saving even if the cache was already empty to update the timestamp.
    self.cached_kml = None
    self.put()

  def GetSortedContents(self):
    """Returns a sorted list of the container content nodes."""
    contents = (self.entity_set, self.link_set, self.folder_set)
    contents = [i.filter('folder', None) for i in contents]
    return sorted(itertools.chain(*contents),
                  key=operator.attrgetter('folder_index'))

  # Shortcuts to use in templates.
  def GetIcons(self):
    return self.GetResources('icon')

  def GetImages(self):
    return self.GetResources('image')

  def GetModels(self):
    return self.GetResources('model')

  def GetModelsInKMZ(self):
    return self.GetResources('model_in_kmz')

  def GetRawResources(self):
    return self.GetResources('raw')


class Resource(db.Model):
  """A Datastore model for arbitrary resources and resource references.

  Explicit Properties:
    layer: A reference to the layer to which this resource belongs.
    filename: The name of the resource as it shows up in the editor. For models
        packed into KMZ, this is also used as to construct a path into the KMZ.
    type: The type of this resource.
    blob: The blob containing the actual data for this resource. Either this or
        external_url must be specified for the resource to be valid.
    external_url: An external URL where the data for this resource is stored.
        Either this or blob must be specified for the resource to be valid.

  Auto-generated Properties:
    style_set: The styles which reference this resource as an icon.
    highlight_style_set: The styles which reference this resource as a highlight
        icon.
    overlay_set: The overlays which reference this resource.
    model_set: The models which reference this resource.

    NOTE: In addition to these, ContainerModelBase also references Resource but
    there's no backreference for it due to circular referencing issues.
  """

  TYPES = ['icon', 'image', 'model', 'model_in_kmz', 'raw']

  layer = db.ReferenceProperty(Layer, required=True)
  filename = db.StringProperty(required=True, indexed=False)
  type = db.StringProperty(choices=TYPES, required=True)
  blob = blobstore.BlobReferenceProperty(indexed=False)
  external_url = db.StringProperty()

  def GetURL(self, absolute=False):
    """Gets the URL of this resource.

    Args:
      absolute: Whether to return an absolute URL.

    Returns:
      The value of external_url if it is defined, or a BlobServer URL for the
      resource otherwise. For models packed into a KMZ, the URL points inside
      the KMZ.
    """
    if self.external_url:
      return self.external_url
    else:
      url = 'r%d' % self.key().id()
      if self.type == 'model_in_kmz':
        url += '.kmz/' + self.filename
      elif self.type == 'model':
        url += '.dae'
      else:
        # NOTE: This logic should be kept in sync with FetchReferencedImages()
        # in the importer's util.py.
        extension = re.search(r'.+\.(\w+)$', self.filename)
        if extension:
          url += '.' + extension.group(1)

      if absolute:
        url = util.GetURL('/serve/0/') + url

      return url

  def GetThumbnailURL(self, size):
    """Gets the URL of a thumbnail version of this resource.

    Args:
      size: The size in pixels of the longer side of the thumbnail.

    Returns:
      If the resource points to an external URL, returns the URL unchanged.
      Otherwise returns a thumbnail URL for the blob.

    Raises:
      TypeError: If the resource is not an image or icon.
    """
    if self.type in ('image', 'icon'):
      if self.external_url:
        return self.external_url
      else:
        return '%s?resize=%d' % (self.GetURL(), size)
    else:
      raise TypeError('Tried to generate thumbnail of a non-image resource.')


class Permission(db.Model):
  """A Datastore model for permission objects that form an Access Control List.

  An ACL is a group of Permission objects belonging to the same layer that
  define how users are allowed to interact with the layer. Possible permissions
  for a user are:
    ACCESS: Ability to see the layer in the editor's layers list and get its KML
        representation.
    MANAGE: Ability to edit layer properties, delete the layer and grant
        pemissions for this layer to other users.
    ENTITIES: Ability to add, edit and remove entities from the layer.
    RESOURCES: Ability to upload and remove resources from the layer.
    STYLES: Ability to add, edit and remove styles from the layer.
    SCHEMAS: Ability to add, edit and remove schemas and templates from the
        layer.

  Every layer must have at least one permission with a MANAGE type. However,
  this is not enforced at the model level.

  Explicit Properties:
    layer: A reference to the layer associated with this permission.
    user: The user to whom this permission relates.
    type: The type of permission granted to the specified user on the layer.
  """

  ACCESS = 'access'
  MANAGE = 'manage'
  ENTITIES = 'entities'
  RESOURCES = 'resources'
  STYLES = 'styles'
  SCHEMAS = 'schemas'
  TYPES = [j for i, j in locals().items() if i.isupper()]

  layer = db.ReferenceProperty(Layer, required=True)
  user = db.UserProperty(required=True)
  type = db.StringProperty(required=True, choices=TYPES)


class Style(db.Model):
  """A Datastore model for style objects to be referenced by entities.

  A Style repesents a set of directives that affect how a particular entity is
  displayed in Google Earth, both in the 3D viewport and in the layers panel.

  Explicit Properties:
    layer: A reference to the layer to which this style belongs.
    name: The name of the style as it appears in the editor.
    icon: A reference to a saved image that is used as the icon for entities
        with this style in both the editor and Google Earth.
    icon_color: The color to blend with the icon.
    icon_scale: A scaling factor to resize the icon - 1.0 is normal size.
    icon_heading: The direction which the icon is facing in degrees.
    label_color: The text color of the label that appears near an entity's icon
        in the 3D view.
    label_scale: A scaling factor to resize the label - 1.0 is normal size.
    balloon_color: The color of the balloon (info window) background.
    text_color: The color of the text in the balloon (info window).
    line_color: The color of the lines used to draw an entity's geometry in the
        3D view.
    line_width: The width of the lines used to draw an entity's geometry in the
        3D view.
    polygon_color: The color of the polygon filling used to draw an entity's
        geometry in the 3D view.
    polygon_fill: Whether to fill the polygon (for entities with polygonal
        geometries).
    polygon_outline: Whether to outline the polygon (for entities with polygonal
        geometries).
    highlight_*: Optional overrides for the above properties activated when the
        user hovers over an entity of this style.
    has_highlight: Whether the layer should take into account highlight
        overrides when generating KML.
    cached_kml: The cached KML representation of the style. This should be reset
        to None whenever the style is updated.

  Auto-generated Properties:
    entity_set: The set of all entities affected by this style.
  """

  layer = db.ReferenceProperty(Layer, required=True)
  name = db.StringProperty(required=True, indexed=False)
  has_highlight = db.BooleanProperty(indexed=False, default=False)

  icon = db.ReferenceProperty(Resource)
  icon_color = db.StringProperty(indexed=False, validator=_ValidateKMLColor)
  icon_scale = db.FloatProperty(indexed=False)
  icon_heading = db.FloatProperty(indexed=False)
  label_color = db.StringProperty(indexed=False, validator=_ValidateKMLColor)
  label_scale = db.FloatProperty(indexed=False)
  balloon_color = db.StringProperty(indexed=False, validator=_ValidateKMLColor)
  text_color = db.StringProperty(indexed=False, validator=_ValidateKMLColor)
  line_color = db.StringProperty(indexed=False, validator=_ValidateKMLColor)
  line_width = db.IntegerProperty(indexed=False)
  polygon_color = db.StringProperty(indexed=False, validator=_ValidateKMLColor)
  polygon_fill = db.BooleanProperty(indexed=False)
  polygon_outline = db.BooleanProperty(indexed=False)

  highlight_icon = db.ReferenceProperty(
      Resource, collection_name='style_highlight_set')
  highlight_icon_color = db.StringProperty(indexed=False,
                                           validator=_ValidateKMLColor)
  highlight_icon_scale = db.FloatProperty(indexed=False)
  highlight_icon_heading = db.FloatProperty(indexed=False)
  highlight_label_color = db.StringProperty(indexed=False,
                                            validator=_ValidateKMLColor)
  highlight_label_scale = db.FloatProperty(indexed=False)
  highlight_balloon_color = db.StringProperty(indexed=False,
                                              validator=_ValidateKMLColor)
  highlight_text_color = db.StringProperty(indexed=False,
                                           validator=_ValidateKMLColor)
  highlight_line_color = db.StringProperty(indexed=False,
                                           validator=_ValidateKMLColor)
  highlight_line_width = db.IntegerProperty(indexed=False)
  highlight_polygon_color = db.StringProperty(indexed=False,
                                              validator=_ValidateKMLColor)
  highlight_polygon_fill = db.BooleanProperty(indexed=False)
  highlight_polygon_outline = db.BooleanProperty(indexed=False)

  cached_kml = db.TextProperty()

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as a KML <Style> or <StyleMap> tag.

    If the style has highlight overrides, two <Style> tags are generated and
    included by a <StyleMap> with the standard ID. Otherwise a single <Style> is
    generated and given the standard ID.

    Returns:
      A string containing a <Style> or two <Style>s and a <StyleMap>.
    """
    if not self.cached_kml or self.layer.uncacheable:
      id_string = str(self.key().id())
      if self.has_highlight:
        normal = self._GenerateSingleStyleKML(id_string + '_1', False)
        highlight = self._GenerateSingleStyleKML(id_string + '_2', True)
        style_map = _RenderKMLTemplate('stylemap.kml', {'style': self})
        kml = ''.join((normal, highlight, style_map))
      else:
        kml = self._GenerateSingleStyleKML(id_string, False)
      self.cached_kml = ForceIntoUnicode(kml)
      if not self.layer.uncacheable: self.put()
    return self.cached_kml

  def _GenerateSingleStyleKML(self, style_id, highlighted):
    """Generates either a normal or a highlight <Style> with the given ID.

    Args:
      style_id: The ID of the generated style element.
      highlighted: Whether to use regular properties or highlighted ones.

    Returns:
      A string containing the <Style>.
    """
    prefix = 'highlight_'
    style = {'layer': self.layer}
    highlight_style = {}
    for name in self.properties():
      value = getattr(self, name)
      if name.startswith(prefix) and value is not None:
        highlight_style[name[len(prefix):]] = value
      else:
        style[name] = value
    if highlighted:
      style.update(highlight_style)

    args = {'id': style_id, 'style': style}

    if self.layer.dynamic_balloons:
      layer_id = self.layer.key().id()
      args['balloon_url'] = util.GetURL('/balloon-raw/%d' % layer_id)

    return _RenderKMLTemplate('style.kml', args)

  def ClearCache(self):
    """Clears the cached KML representation of this style."""
    self.layer.ClearCache()
    if self.cached_kml:
      self.cached_kml = None
      self.put()


class Region(db.Model):
  """A Datastore model for regions that define when to show and load entities.

  A Region is a 2D or 3D box, which shows or hides associated entities
  depending on whether the camera is inside or outside its bounds.

  Explicit Properties:
    layer: A reference to the layer to which this region belongs.
    name: The name of this region.
    north: The latitude of the north edge of the region, in degrees.
    south: The latitude of the south edge of the region, in degrees.
    east: The longitude of the east edge of the region, in degrees.
    west: The longitude of the west edge of the region, in degrees.
    min_altitude: The altitude of the bottom edge of the region, in meters.
    max_altitude: The altitude of the top edge of the region, in meters.
    altitude_mode: A choice of how to interpret the altitude property.
    lod_min: The minimum number pixels that the region has to take up on the
        screen to be activated.
    lod_max: The maximum number pixels that the region can take up on the screen
        before being deactivated.
    lod_fade_min: The number of pixels away from lod_min over which the region
        fades in. See the official KML reference for more info.
    lod_fade_max: The number of pixels away from lod_max over which the region
        fades out. See the official KML reference for more info.
    cached_kml: The cached KML representation of the region. This should be
        reset to None whenever the region is updated.
    timestamp: The last modified timestamp.

  Auto-generated Properties:
    entity_set: The set of all entities that reference this region.
    folder_set: The set of all folders that reference this region.
    link_set: The set of all links that reference this region.
  """
  layer = db.ReferenceProperty(Layer, required=True)
  name = db.StringProperty(indexed=False)
  north = db.FloatProperty(required=True, indexed=False)
  south = db.FloatProperty(required=True, indexed=False)
  west = db.FloatProperty(required=True, indexed=False)
  east = db.FloatProperty(required=True, indexed=False)
  min_altitude = db.FloatProperty(indexed=False)
  max_altitude = db.FloatProperty(indexed=False)
  altitude_mode = db.StringProperty(choices=_ALTITUDE_MODES, indexed=False)
  lod_min = db.IntegerProperty(indexed=False)
  lod_max = db.IntegerProperty(indexed=False)
  lod_fade_min = db.IntegerProperty(indexed=False)
  lod_fade_max = db.IntegerProperty(indexed=False)
  cached_kml = db.TextProperty()
  timestamp = db.DateTimeProperty(auto_now=True)

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as a KML <Region> tag.

    Returns:
      A string containing a KML <Region> tag.
    """
    if not self.cached_kml or self.layer.uncacheable:
      kml = ForceIntoUnicode(_RenderKMLTemplate('region.kml', {'region': self}))
      self.cached_kml = kml
      if not self.layer.uncacheable: self.put()
    return self.cached_kml

  def ClearCache(self):
    """Clears the cached KML representation of this region."""
    self.layer.ClearCache()
    if self.cached_kml:
      self.cached_kml = None
      self.put()


class Folder(ContainerModelBase):
  """A Datastore model for folder objects used to organize entities.

  A Folder repesents a node in the browsable tree of entities. Folders can have
  other folders as parents to create a tree structure. Parentless folders are
  considered to be the children of the layer.

  Explicit Properties:
    layer: A reference to the layer to which this folder belongs.
    layer_timestamp: The last modified timestamp of the layer that contains this
        folder.
    folder: A reference to another folder that is the parent of this one. If
        None, the folder is considered a child of the layer.
    folder_index: A number indicating where in the parent folder the folder
        appears. Entities, folders or links with lower indices appear before
        those with higher ones.
    region: The Region that controls when this folder is shown or hidden.
    region_timestamp: The last modified timestamp of the region used by this
        folder.
    cached_kml: The cached KML representation of the folder. This should be
        reset to None whenever the folder is updated.

  Properties inherited from ContainerModelBase:
    name, description, icon, custom_kml, item_type: See the ContainerModelBase
    docstring for details.

  Auto-generated Properties:
    entity_set: The set of all entities which are inside this folder.
    folder_set: The set of all folders which are inside this folder.
    link_set: The set of all links which are inside this folder.
  """

  layer = db.ReferenceProperty(Layer, required=True)
  layer_timestamp = db.DateTimeProperty()
  folder = db.SelfReferenceProperty()
  folder_index = db.IntegerProperty(default=0)
  region = db.ReferenceProperty(Region)
  region_timestamp = db.DateTimeProperty()
  cached_kml = db.TextProperty()

  def GenerateKML(self, cache=None):
    """Serializes the object as a KML <Folder> tag.

    Args:
      cache: An optional collections.defaultdict to use as a cache.

    Returns:
      A string containing a KML <Folder> tag.
    """
    if (not self.cached_kml or
        self.layer.uncacheable or
        self.layer.timestamp != self.layer_timestamp or
        (self.region and self.region.timestamp != self.region_timestamp)):
      contents = [i.GenerateKML(cache) for i in self.GetSortedContents()]
      description = self.EvaluateDescription()
      args = {'folder': self, 'contents': contents, 'description': description}
      self.cached_kml = ForceIntoUnicode(_RenderKMLTemplate('folder.kml', args))
      self.layer_timestamp = self.layer.timestamp
      if self.region: self.region_timestamp = self.region.timestamp
      if not self.layer.uncacheable: self.put()
    return self.cached_kml

  def ClearCache(self):
    """Clears the cached KML representation of this folder."""
    self.layer.ClearCache()
    if self.cached_kml:
      self.cached_kml = None
      self.put()

  def GetSortedContents(self):
    """Returns a sorted list of the container content nodes."""
    contents = (self.entity_set, self.link_set, self.folder_set)
    return sorted(itertools.chain(*contents),
                  key=operator.attrgetter('folder_index'))


class Link(ContainerModelBase):
  """A Datastore model for arbitrary network links.

  A Link repesents a node in the browsable tree of entities whose contents are
  fetched dynamically from another KML file. It can have an associated Region to
  control when the link is loaded or shown.

  Explicit Properties:
    layer: A reference to the layer to which this link belongs.
    url: The URL of the KML file to which this link points.
    folder: A reference to the folder which contains this link. None means the
        layer root.
    folder_index: A number indicating where in the folder the link appears.
        Entities, folders or links with lower indices appear before those with
        higher ones.
    region: The Region that controls when the KML pointed to by this link is
        loaded, shown and hidden.
    region_timestamp: The last modified timestamp of the region used by this
        link.
    cached_kml: The cached KML representation of the link. This should be
        reset to None whenever the link is updated.

  Properties inherited from ContainerModelBase:
    name, description, icon, custom_kml, item_type: See the ContainerModelBase
    docstring for details.
  """

  layer = db.ReferenceProperty(Layer, required=True)
  url = db.StringProperty(required=True, indexed=False)
  folder = db.ReferenceProperty(Folder)
  folder_index = db.IntegerProperty(default=0)
  region = db.ReferenceProperty(Region)
  region_timestamp = db.DateTimeProperty()
  cached_kml = db.TextProperty()

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as a KML <NetworkLink> tag.

    Returns:
      A string containing a KML <NetworkLink> tag.
    """
    if (not self.cached_kml or
        self.layer.uncacheable or
        (self.region and self.region.timestamp != self.region_timestamp)):
      description = self.EvaluateDescription()
      args = {'link': self, 'description': description}
      self.cached_kml = ForceIntoUnicode(_RenderKMLTemplate('link.kml', args))
      if self.region: self.region_timestamp = self.region.timestamp
      if not self.layer.uncacheable: self.put()
    return self.cached_kml

  def ClearCache(self):
    """Clears the cached KML representation of this link."""
    self.layer.ClearCache()
    if self.cached_kml:
      self.cached_kml = None
      self.put()


class Schema(db.Model):
  """A Datastore model for schema objects that defines a fieldset for entities.

  A Schema repesents a set of fields and templates which an entity uses to
  define custom data, and which are then used to generate an HTML page to be
  used in the entity bubble (a.k.a. balloon, a.k.a. info window) when it is
  displayed in Google Earth.

  Explicit Properties:
    layer: A reference to the layer to which this schema belongs.
    name: The name of the schema as it shows up in the editor.

  Auto-generated Properties:
    template_set: The set of all templates which use this schema.
    field_set: The set of all fields of which this schema consists.
  """

  layer = db.ReferenceProperty(Layer, required=True)
  name = db.StringProperty(required=True, indexed=False)

  def SafeDelete(self):
    """Deletes the schema and its templates and fields in a transaction."""

    def Delete():
      for field in self.field_set.ancestor(self):
        field.delete()
      # pylint: disable-msg=W0621
      for template in self.template_set.ancestor(self):
        template.delete()
      self.delete()
    db.run_in_transaction(Delete)


class Template(db.Model):
  """A DataStore model for a info window template object.

  Explicit Properties:
    schema: A reference to the schema to which this template belongs.
    name: The name of the template as it shows up in the editor.
    text: The text of the Django v0.96 template that will be evaluated on
        entities to generate the contents of their info windows. The contents of
        this fields are not escaped when generating KML, and can therefore
        contain HTML and scripts.
    timestamp: The last modified timestamp.

  Auto-generated Properties:
    entity_set: The set of all entities that use this template.
  """

  schema = db.ReferenceProperty(Schema, required=True)
  name = db.StringProperty(required=True, indexed=False)
  text = db.TextProperty(validator=_ValidateDjangoTemplate)
  timestamp = db.DateTimeProperty(auto_now=True)

  def Evaluate(self, entity, cache=None, link_template=None):
    """Evaluates the template in the context of an entity's fields.

    Args:
      entity: The entity whose values to use as the context when evaluating the
          template.
      cache: An optional collections.defaultdict to use as a cache.
      link_template: An optional string to use as a template when creating
          inter-entity links. Used when dynamically serving balloons since we
          cannot use the ordinary hash-id notation in dynamic content.

    Returns:
      A string containing the results of evaluating the template on the
      specified entity.
    """
    template_id = self.key().id()
    if cache is not None:
      template_cache = cache['entity_templates']
    else:
      template_cache = {}

    if template_id not in template_cache:
      template.register_template_library('template_functions.entities')
      if isinstance(self.text, unicode):
        encoded_text = self.text.encode('utf8')
      else:
        encoded_text = self.text
      template_cache[template_id] = template.Template(encoded_text)

    args = {
        'entity': entity,
        '_cache': cache,
        '_link_template': link_template,
    }
    for field in self.schema.field_set:
      value = getattr(entity, 'field_' + field.name, '')
      if field.type in ('image', 'icon', 'resource') and value:
        value = util.GetInstance(Resource, value, entity.layer).GetURL()
      args[field.name] = value

    return template_cache[template_id].render(template.Context(args))

  def ClearCache(self):
    """Clears the cached KML of the whole layer to force entity cache checks."""
    self.schema.layer.ClearCache()


class Field(db.Model):
  """A DataStore model for a schema field object.

  Explicit Properties:
    schema: A reference to the schema to which this field belongs.
    name: An alphanumeric identifier for the field unique to a particular scheme
        that is used in the editor and referenced in templates.
    tip: A freetext description of the field that appears as a hover tip to the
        user in the editor.
    type: The data type of the field's content, used by Validate().
  """

  TYPES = ['string', 'text', 'integer', 'float', 'date', 'color', 'image',
           'icon', 'resource']

  schema = db.ReferenceProperty(Schema, required=True)
  name = db.StringProperty(required=True)
  tip = db.StringProperty(indexed=False)
  type = db.StringProperty(choices=TYPES, indexed=False, required=True)

  def Validate(self, value):
    """Validates, cleans and typecasts the given value for use for this field.

    The values considered valid for each type are as follows:
      string and text: A string (ASCII, UTF8 or unicode). Returned converted to
          unicode if it's not already.
      integer: Anything that can be successfully casted into a long. Returned as
          a long.
      float: Anything that can be successfully casted into a float. Returned as
          a float.
      date: A string containing a date or a datetime in the strftime formats
          "%Y-%m-%d" and "%Y-%m-%d %H:%M:%S" respectively. Returned as a
          datetime.datetime object.
      color: An 8-character string specifying the color in the AABBGGRR format.
          Returned in lowercase.
      resource: The ID of a Resource in the same layer. Returned untouched.

    Args:
      value: The value to check.

    Returns:
      The value casted to the appropriate type if it's valid. None otherwise.

    Raises:
      TypeError: When the field has an unrecognized type.
    """
    if self.type in ('string', 'text'):
      if isinstance(value, unicode):
        cleaned = value
      elif isinstance(value, basestring):
        try:
          cleaned = value.decode('utf8')
        except UnicodeDecodeError:
          return None
      else:
        return None

      if self.type == 'text':
        return db.Text(cleaned)
      else:
        return cleaned
    elif self.type == 'integer':
      try:
        return long(value)
      except (ValueError, TypeError):
        return None
    elif self.type == 'float':
      try:
        return float(value)
      except (ValueError, TypeError):
        return None
    elif self.type == 'date':
      try:
        try:
          parsed_time = time.strptime(value, '%Y-%m-%d')
        except (ValueError, TypeError):
          parsed_time = time.strptime(value, '%Y-%m-%d %H:%M:%S')
        return datetime.datetime(*parsed_time[:6])
      except (ValueError, TypeError):
        return None
    elif self.type == 'color':
      try:
        _ValidateKMLColor(value)
      except ValueError:
        return None
      return value.lower()
    elif self.type in ('image', 'icon', 'resource'):
      layer = self.schema.layer
      try:
        resource = util.GetInstance(Resource, value, layer, required=False)
      except util.BadRequest:
        return None
      if resource:
        if self.type not in ('resource', resource.type):
          return None
        return value
      else:
        return None
    else:
      raise TypeError('This field has an invalid type.')


class Geometry(polymodel.PolyModel):
  """An abstract base class for Datastore models of geometry objects.

  A Geometry object represents an object to be displayed in the 3D viewport
  including all its properties. Geometries here do not necessarily correspond
  directly to KML Geometry objects. Should not be instantiated directly.
  """

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as KML.

    Some subclasses will return subtypes of the KML <Geometry> tag, while others
    will return subtypes of the <Feature> tag.
    """
    raise NotImplementedError('Subclasses must implement KML generation.')


class KMLGeometry(Geometry):
  """A base class for geometries that mirror a sybtype of the KML <Geometry>.

  Despite the lack of functionality, this is useful so that clients can simply
  check for isinstance(a_geometry_object, KMLGeometry) to determine how to use
  the resulting KML. Should not be instantiated directly.
  """
  pass


class Overlay(Geometry):
  """A base class for geometries that mirror a sybtype of the KML <Overlay>.

  Should not be instantiated directly.

  Explicit Properties:
    image: A reference to the image on the surface of the overlay.
    color: The color of the overlay in AABBGGRR hexadecimal format.
    draw_order: A number that determines the stacking order of overlays.
        Overlays with higher draw_order values are drawn on top of overlays with
        lower ones.
  """
  image = db.ReferenceProperty(Resource, required=True)
  color = db.StringProperty(indexed=False, validator=_ValidateKMLColor)
  draw_order = db.IntegerProperty(indexed=False)


class Point(KMLGeometry):
  """A Datastore model for point objects.

  Explicit Properties:
    location: A latitude, longitude pair indicating the position of the point.
    altitude: The altitude of the point.
    altitude_mode: A choice of how to interpret the altitude property.
    extrude: A boolean indicating whether the point should have a line
        connecting it to the ground rendered.
  """

  location = db.GeoPtProperty(indexed=False, required=True)
  altitude = db.FloatProperty(indexed=False)
  altitude_mode = db.StringProperty(choices=_ALTITUDE_MODES, indexed=False)
  extrude = db.BooleanProperty(indexed=False)

  def GetCenter(self):
    """Returns a db.GeoPt with the location of the center of this geometry."""
    return self.location

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as a <Point>."""
    return ForceIntoUnicode(_RenderKMLTemplate('point.kml', {'point': self}))


class LineString(KMLGeometry):
  """A Datastore model for line string objects.

  Explicit Properties:
    points: A list of latitude, longitude pairs describing the points between
        which the line runs.
    altitudes: The altitude of each point. Must be of the same length as points
        or None (in which case all altitudes are set to 0).
    altitude_mode: A choice of how to interpret the altitudes property.
    tesselate: A boolean indicating whether the lines should be broken up to
        follow the contour of the underlying terrain.
    extrude: A boolean indicating whether the lines should be extruded from
        the ground to their altitude to appear as vertical planes instead.
  """

  points = db.ListProperty(db.GeoPt, required=True, indexed=False)
  altitudes = db.ListProperty(float, indexed=False)
  altitude_mode = db.StringProperty(choices=_ALTITUDE_MODES, indexed=False)
  tessellate = db.BooleanProperty(indexed=False)
  extrude = db.BooleanProperty(indexed=False)

  def GetCenter(self):
    """Returns a db.GeoPt with the location of the center of this geometry."""
    latitude = sum(i.lat for i in self.points) / len(self.points)
    longitude = sum(i.lon for i in self.points) / len(self.points)
    return db.GeoPt(latitude, longitude)

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as a <LineString>."""
    kml = _RenderKMLTemplate('line_string.kml', {'line_string': self})
    return ForceIntoUnicode(kml)


class Polygon(KMLGeometry):
  """A Datastore model for arbitrary polygon objects.

  Explicit Properties:
    outer_points: A list of latitude, longitude pairs describing the outer
        boundary of the polygon.
    inner_points: A list of latitude, longitude pair describing the inner
        boundary of the polygon (if any).
    outer_altitudes: The altitude of each point of the outer boundary. Must be
        of the same length as outer_points or None (in which case all altitudes
        are set to 0).
    inner_altitudes: The altitude of each point of the inner boundary. Must be
        of the same length as inner_points or None (in which case all altitudes
        are set to 0).
    altitude_mode: A choice of how to interpret the altitudes property.
    tesselate: A boolean indicating whether the polygon should follow the
        contour of the underlying terrain.
    extrude: A boolean indicating whether the polygon should be extruded from
        the ground to its altitude to look 3-dimensional.
  """

  outer_points = db.ListProperty(db.GeoPt, required=True, indexed=False)
  inner_points = db.ListProperty(db.GeoPt, indexed=False)
  outer_altitudes = db.ListProperty(float, indexed=False)
  inner_altitudes = db.ListProperty(float, indexed=False)
  altitude_mode = db.StringProperty(choices=_ALTITUDE_MODES, indexed=False)
  tessellate = db.BooleanProperty(indexed=False)
  extrude = db.BooleanProperty(indexed=False)

  def GetCenter(self):
    """Returns a db.GeoPt with the location of the center of this geometry."""
    latitude = sum(i.lat for i in self.outer_points) / len(self.outer_points)
    longitude = sum(i.lon for i in self.outer_points) / len(self.outer_points)
    return db.GeoPt(latitude, longitude)

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as a <Polygon>."""
    kml = _RenderKMLTemplate('polygon.kml', {'polygon': self})
    return ForceIntoUnicode(kml)


class Model(KMLGeometry):
  """A Datastore model for 3D model objects.

  Explicit Properties:
    model: The URL of the COLLADA 3D model to reference.
    location: A latitude, longitude pair that indicates the location of the
        model.
    altitude: The altitude of the model.
    altitude_mode: A choice of how to interpret the altitude property.
    heading: Rotation in degrees about the Z (perpendicular to the ground) axis.
    tilt: Rotation in degrees about the X axis.
    roll: Rotation in degrees about the Y axis.
    scale_x: The scale ratio in the X axis.
    scale_y: The scale ratio in the Y axis.
    scale_z: The scale ratio in the Z axis.
    resource_alias_sources: A list of resource filepaths that occur in the
        COLLADA file and which should be replaced with alternative paths.
    resource_alias_targets: A list of Resource IDs for images that should
        replace the ones in the resource_alias_sources list, respectively.
  """

  model = db.ReferenceProperty(Resource)
  location = db.GeoPtProperty(indexed=False, required=True)
  altitude = db.FloatProperty(indexed=False)
  altitude_mode = db.StringProperty(choices=_ALTITUDE_MODES, indexed=False)
  heading = db.FloatProperty(indexed=False)
  tilt = db.FloatProperty(indexed=False)
  roll = db.FloatProperty(indexed=False)
  scale_x = db.FloatProperty(indexed=False)
  scale_y = db.FloatProperty(indexed=False)
  scale_z = db.FloatProperty(indexed=False)
  resource_alias_sources = db.StringListProperty(indexed=False)
  resource_alias_targets = db.ListProperty(int, indexed=False)

  def GetCenter(self):
    """Returns a db.GeoPt with the location of the center of this geometry."""
    return self.location

  def GenerateKML(self, unused_cache=None):
    """Serializes the object as a <Model>.

    Returns:
      A string containing the KML representation of the model in a <Model> tag.

    Raises:
      KMLGenerationError: When the number of resource alias targets differs from
      the number of resource alias sources.
    """
    if len(self.resource_alias_sources) != len(self.resource_alias_targets):
      raise KMLGenerationError('The number of resource alias sources differs '
                               'from the number of resource alias targets.')

    targets = [Resource.get_by_id(i) for i in self.resource_alias_targets]
    resource_map = zip(self.resource_alias_sources, targets)
    args = {'model': self, 'resource_map': resource_map}
    return ForceIntoUnicode(_RenderKMLTemplate('model.kml', args))


class GroundOverlay(Overlay):
  """A Datastore model for rectangular ground overlay objects.

  Explicit Properties:
    north: The maximum latitude of the overlay rectangle.
    south: The minimum latitude of the overlay rectangle.
    east: The maximum longitude of the overlay rectangle.
    west: The minimum longitude of the overlay rectangle.
    rotation: The rotation of the overlay rectangle around the Z axis, in
        degrees.
    altitude: The altitude of the overlay.
    altitude_mode: A choice of how to interpret the altitude property.
    is_quad: Whether the ground overlay is not a box parallel to the latitude
        and longitude lines, and should use the corners property to define its
        quad. If this is True, north, south, east, west and rotation properties
        are ignored. Otherwise the corners property is ignored.
    corners: A list of 4 GeoPt objects, specified in counter-clockwise order
        with the first point corresponding to the lower-left corner of the
        overlayed image. The shape described by these corners must be convex.

  Properties Inherited from Overlay:
    image, color, draw_order: See the Overlay docstring for details.
  """

  north = db.FloatProperty(indexed=False)
  south = db.FloatProperty(indexed=False)
  west = db.FloatProperty(indexed=False)
  east = db.FloatProperty(indexed=False)
  rotation = db.FloatProperty(indexed=False)
  altitude = db.FloatProperty(indexed=False)
  altitude_mode = db.StringProperty(choices=_ALTITUDE_MODES, indexed=False)
  is_quad = db.BooleanProperty(indexed=False)
  corners = db.ListProperty(db.GeoPt, indexed=False)

  def GetCenter(self):
    """Returns a db.GeoPt with the location of the center of this geometry."""
    if self.is_quad:
      latitude = longitude = 0
      for corner in self.corners[:4]:
        latitude += corner.lat
        longitude += corner.lon
      latitude /= 4
      longitude /= 4
    else:
      latitude = (self.north + self.south) / 2
      longitude = (self.east + self.west) / 2
    return db.GeoPt(latitude, longitude)

  def GenerateKML(self, entity_id, feature_contents, unused_cache=None):
    """Serializes the object as a <GroundOverlay>.

    Args:
      entity_id: The ID of the entity to which this geometry belongs.
      feature_contents: A string containing the Feature-specific tags that have
          to be included into the <GroundOverlay>.

    Returns:
      A complete <GroundOverlay> tag with both the Overlay-specific and the
      Feature-specific tags.
    """
    kml = _RenderKMLTemplate('ground_overlay.kml', {
        'ground_overlay': self, 'id': entity_id, 'feature': feature_contents})
    return ForceIntoUnicode(kml)


class PhotoOverlay(Overlay):
  """A Datastore model for 3D photo overlay objects.

  Explicit Properties:
    location: A latitude, longitude pair that indicates the location of the
        overlay.
    altitude: The altitude of the overlay.
    rotation: The rotation of the photo placed inside the field of view.
    shape: The shape of the overlay onto which the photo is projected.
    view_left: Angle, in degrees, between the camera's viewing direction and the
        left side of the view volume.
    view_right: Angle, in degrees, between the camera's viewing direction and
        the right side of the view volume.
    view_top: Angle, in degrees, between the camera's viewing direction and the
        top side of the view volume.
    view_bottom: Angle, in degrees, between the camera's viewing direction and
        the bottom side of the view volume.
    view_near: Distance in meters along the viewing direction from the camera
        viewpoint to the overlay shape.
    pyramid_tile_size: For images divided into a pyramid, the size of each
        pyramid tile, in pixels. Tiles must be square, and pyramid_tile_size
        must be a power of 2. A tile size of 256 or 512 is recommended. The
        original image is divided into tiles of this size, at varying
        resolutions.
    pyramid_height: For images divided into a pyramid, the height of the
        original image, in pixels.
    pyramid_width: For images divided into a pyramid, the width of the original
        image, in pixels.
    pyramid_grid_origin: For images divided into a pyramid, where to begin
        numbering the tiles in each layer of the pyramid. A value of lowerLeft
        specifies that row 1, column 1 of each layer is in the bottom left
        corner of the grid, while a value of upperLeft specifies that row 1,
        column 1 of each layer is in the top left corner of the grid.

  Properties Inherited from Overlay:
    image, color, draw_order: See the Overlay docstring for details.
  """

  SHAPES = ['rectangle', 'cylinder', 'sphere']
  GRID_ORIGINS = ['lowerLeft', 'upperLeft']

  location = db.GeoPtProperty(indexed=False, required=True)
  altitude = db.FloatProperty(indexed=False)
  rotation = db.FloatProperty(indexed=False)
  shape = db.StringProperty(choices=SHAPES, required=True, indexed=False)
  view_left = db.FloatProperty(indexed=False, required=True)
  view_right = db.FloatProperty(indexed=False, required=True)
  view_top = db.FloatProperty(indexed=False, required=True)
  view_bottom = db.FloatProperty(indexed=False, required=True)
  view_near = db.FloatProperty(indexed=False, required=True)
  pyramid_tile_size = db.IntegerProperty(indexed=False)
  pyramid_height = db.IntegerProperty(indexed=False)
  pyramid_width = db.IntegerProperty(indexed=False)
  pyramid_grid_origin = db.StringProperty(indexed=False, choices=GRID_ORIGINS)

  def GetCenter(self):
    """Returns a db.GeoPt with the location of the center of this geometry."""
    return self.location

  def GenerateKML(self, entity_id, feature_contents, unused_cache=None):
    """Serializes the object as a <PhotoOverlay>.

    Args:
      entity_id: The ID of the entity to which this geometry belongs.
      feature_contents: A string containing the Feature-specific tags that have
          to be included into the <PhotoOverlay>.

    Returns:
      A complete <PhotoOverlay> tag with both the Overlay-specific and the
      Feature-specific tags.
    """
    args = {'photo_overlay': self, 'id': entity_id, 'feature': feature_contents}
    return ForceIntoUnicode(_RenderKMLTemplate('photo_overlay.kml', args))


class Division(db.Model):
  """A Datastore model for layer divisions, used for auto-regionation.

  Explicit Properties:
    layer: A reference to the layer to which this division belongs.
    layer_timestamp: The last modified timestamp of the layer that contains this
        division.
    north: The maximum latitude of the overlay rectangle.
    south: The minimum latitude of the overlay rectangle.
    west: The maximum longitude of the overlay rectangle.
    east: The minimum longitude of the overlay rectangle.
    baked: Whether the division has been baked already.
    entities: A list of IDs of entity that belong to this division.
    parent_division: The Division which contains this one. None for roots.
    cached_kml: The cached KML representation of the division. This should be
        reset to None whenever the division is updated.

  Auto-generated Properties:
    division_set: The set of all child divisions.
  """

  layer = db.ReferenceProperty(Layer, required=True)
  layer_timestamp = db.DateTimeProperty()
  north = db.FloatProperty(required=True)
  south = db.FloatProperty(required=True)
  west = db.FloatProperty(required=True)
  east = db.FloatProperty(required=True)
  baked = db.BooleanProperty(required=True)
  entities = db.ListProperty(int)
  parent_division = db.SelfReferenceProperty()
  cached_kml = db.TextProperty()

  def GenerateKML(self, cache=None):
    """Serializes the division as a lightweight KML <Document> tag.

    Args:
      cache: An optional collections.defaultdict to use as a cache.

    Returns:
      A string containing the KML code for a <Document>.

    Raises:
      KMLGenerationError: If the division has not finished baking yet.
    """
    if not self.baked:
      raise KMLGenerationError('Cannot generate unbaked layer division.')

    if (not self.cached_kml or self.layer.uncacheable or
        self.layer.timestamp != self.layer_timestamp):
      entities = [i.GenerateKML(cache) for i in Entity.get_by_id(self.entities)]
      links_kml = [i.GenerateLinkKML() for i in self.division_set]
      args = {'layer': self, 'contents': entities + links_kml}
      self.cached_kml = ForceIntoUnicode(_RenderKMLTemplate('layer.kml', args))
      self.layer_timestamp = self.layer.timestamp
      if not self.layer.uncacheable: self.put()
    return self.cached_kml

  def GenerateLinkKML(self):
    """Generates a <NetworkLink> tag pointing to this division."""
    return _RenderKMLTemplate('division_link.kml', {'division': self})

  def ClearCache(self):
    """Clears the cached KML representation of this division."""
    if self.cached_kml:
      self.cached_kml = None
      self.put()


class Entity(geomodel.GeoModel, db.Expando):
  """A Datastore expando model for entity objects.

  Explicit Properties:
    layer: A reference to the layer to which this entity belongs.
    layer_timestamp: The last modified timestamp of the layer that contains this
        entity.
    name: The name of the entity as it shows up in the editor and in Google
        Earth.
    geometries: A list of IDs of Geometry objects that belong to this entity.
    snippet: A brief description of the entity that is used in the places panel
        of Google Earth.
    folder: A reference to the folder which contains this entity.
    folder_index: A number indicating where in the folder the entity appears.
        Entities, folders or links with lower indices appear before those with
        higher ones.
    template: A reference to the template which this entity uses, and indirectly
        to the schema which the template belongs to.
    template_timestamp: The last modified timestamp of the template used by this
        entity.
    style: A reference to the style which is applied to the entity.
    region: The Region that controls when this entity is shown or hidden.
    region_timestamp: The last modified timestamp of the region used by this
        entity.
    view_location: The latitude and longitude of the point to which the camera
        points when displaying this entity.
    view_altitude: The altitude of the point to which the camera points when
        displaying this entity.
    view_heading: The direction (in degrees) of the point to which the camera
        points when displaying this entity.
    view_tilt: The angle (in degrees) between the direction of the camera when
        displaying this entity and the normal to the surface of the earth.
        Values range from 0 to 90 degrees. A value of 0  indicates viewing from
        directly above, while a value of 90 degrees indicates viewing along the
        horizon.
    view_roll: Rotation, in degrees, of the camera around the Z axis. Ignored if
        view_is_camera is False.
    view_range: Distance in meters from the point specified by location and
        altitude to the camera. Ignored if view_is_camera is True.
    view_is_camera: Whether the view_* properties define the position of the
        camera rather than the target.
    priority: This entity's priority. Used during auto-regionation for selecting
        entities to display in larger regions. Ignored for non-auto-managed
        layers.
    baked: Used during regionation to mark that the entity has already been
        assigned to a particular subdivision of the layer. Ignored for
        non-auto-managed layers.
    cached_kml: The cached KML representation of the entity. This should be
        reset to None whenever the entity is updated.

  GeoModel Properties:
    location: The location of the centerpoint of this model's geometry.
    location_geocells: A list of "geocell" strings that can be used to perform
      bounding box queries on location via GeoModel.bounding_box_fetch().

  Dynamic Properties:
    For each field in the schema that the entity uses (indirectly, through a
    template), there may be a dynamic property called field_{field name}.
  """

  layer = db.ReferenceProperty(Layer, required=True)
  layer_timestamp = db.DateTimeProperty()
  name = db.StringProperty(required=True, indexed=False)
  geometries = db.ListProperty(int)
  snippet = db.StringProperty(indexed=False, multiline=True)
  folder = db.ReferenceProperty(Folder)
  folder_index = db.IntegerProperty()
  template = db.ReferenceProperty(Template)
  template_timestamp = db.DateTimeProperty()
  style = db.ReferenceProperty(Style)
  region = db.ReferenceProperty(Region)
  region_timestamp = db.DateTimeProperty()

  view_location = db.GeoPtProperty(indexed=False)
  view_altitude = db.FloatProperty(indexed=False)
  view_heading = db.FloatProperty(indexed=False)
  view_tilt = db.FloatProperty(validator=_ValidateTilt, indexed=False)
  view_roll = db.FloatProperty(indexed=False)
  view_range = db.FloatProperty(indexed=False)
  view_is_camera = db.BooleanProperty(indexed=False)

  priority = db.FloatProperty()
  baked = db.BooleanProperty()

  cached_kml = db.TextProperty()

  bounding_box_fetch = staticmethod(geomodel.GeoModel.bounding_box_fetch)

  def GenerateKML(self, cache=None):
    """Serializes the object as one or more KML Features.

    If the entity has only one geometry, only one tag is returned. This tag will
    have the standard entity ID.

    If all of this entity's geometries are subtypes of KML Geometry, stuffs them
    all into a single <Placemark> tag with a <MultiGeometry>. In this case the
    placemark also has a standard ID.

    If the entity has multiple Overlay geometry, or a mix or KMLGeometry and
    Overlay geometries, creates a main Feature tag with the standard ID, and a
    collection of additional Features with suffixed IDs.

    Args:
      cache: An optional collections.defaultdict to use as a cache.

    Returns:
      A string containing one or more KML tags, each a subtypes of the KML
      <Feature> tag.

    Raises:
      ValueError: If the entity has no geometries.
    """
    if (not self.cached_kml or
        self.layer.uncacheable or
        self.layer.timestamp != self.layer_timestamp or
        (self.region and self.region.timestamp != self.region_timestamp) or
        (self.template and self.template.timestamp != self.template_timestamp)):
      kml = ForceIntoUnicode(self._DoGenerateKML(cache))
      self.cached_kml = kml
      self.layer_timestamp = self.layer.timestamp
      if self.region: self.region_timestamp = self.region.timestamp
      if self.template: self.template_timestamp = self.template.timestamp
      if not self.layer.uncacheable: self.put()
    return self.cached_kml

  def _DoGenerateKML(self, cache):
    """Actually implements KML generation as described in GenerateKML()."""
    if not self.geometries:
      raise ValueError('An entity must have at least one geometry.')

    description = ''
    if not self.layer.dynamic_balloons and self.template:
      description = self.template.Evaluate(self, cache)

    args = {'entity': self, 'description': description}
    feature_details = ForceIntoUnicode(_RenderKMLTemplate('entity.kml', args))

    geometries = [Geometry.get_by_id(i, parent=self) for i in self.geometries]

    kml_geometries = [i for i in geometries if isinstance(i, KMLGeometry)]
    overlays = [i for i in geometries if not isinstance(i, KMLGeometry)]

    if kml_geometries:
      kml_geometries_kml = ''.join(i.GenerateKML(cache)
                                   for i in kml_geometries)
      if len(geometries) > 1:
        kml_geometries_kml = (u'<MultiGeometry>%s</MultiGeometry>' %
                              kml_geometries_kml)
      main_feature = (u'<Placemark id="id%d">%s%s</Placemark>' %
                      (self.key().id(), feature_details, kml_geometries_kml))
    else:
      main_feature = ''

    if overlays and not main_feature:
      first_overlay = overlays[0]
      overlays = overlays[1:]
      main_feature = first_overlay.GenerateKML(self.key().id(), feature_details,
                                               cache)

    if overlays:
      # Make sure only the first Feature has a balloon.
      args = {'entity': self, 'description': ''}
      feature_details = _RenderKMLTemplate('entity.kml', args)

      overlays_kml = []
      for index, overlay in enumerate(overlays):
        overlay_id = '%d_%d' % (self.key().id(), index)
        overlays_kml.append(overlay.GenerateKML(overlay_id, feature_details,
                                                cache))
      extra_features = ''.join(overlays_kml)
    else:
      extra_features = ''

    return main_feature + extra_features

  def UpdateLocation(self, geometry=None):
    """Synchronizes the entity's location and geocells with its geometry.

    If a geometry is specified, syncs to it. Otherwise syncs to the first
    geometry of this entity. The entity's location is set to the centerpoint
    of that geometry.

    Args:
      geometry: The geometry to synchronize to. Optional.

    Raises:
      ValueError: If the entity has no geometries.
    """
    if not self.geometries:
      raise ValueError('An entity must have at least one geometry.')
    if not geometry:
      geometry = Geometry.get_by_id(self.geometries[0], parent=self)
    self.location = geometry.GetCenter()
    geomodel.GeoModel.update_location(self)

  def SafeDelete(self):
    """Deletes the entity and its geometry in a transaction."""

    def Delete():
      for geometry_id in self.geometries:
        Geometry.get_by_id(geometry_id, parent=self).delete()
      self.delete()
    db.run_in_transaction(Delete)

  def ClearCache(self):
    """Clears the cached KML representation of this entity."""
    self.layer.ClearCache()
    if self.cached_kml:
      self.cached_kml = None
      self.put()
