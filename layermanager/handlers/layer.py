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

"""The layer editing page of the KML Layer Manager."""

from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.api import users
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors
import handlers.base
import model
import util


class LayerHandler(handlers.base.PageHandler):
  """A form to create or edit a layer."""

  PERMISSION_REQUIRED = model.Permission.MANAGE
  REQUIRES_LAYER = False
  FORM_TEMPLATE = 'layer'
  ASSOCIATED_MODEL = model.Layer

  def ShowForm(self, _):
    """Shows a layer editing form."""
    return {'layer_model': model.Layer}

  def ShowRaw(self, layer):
    """Writes out a JSON representation of the layer.

    GET Args:
      id: The ID of the layer. Redundant, but used for consistency.
      nocontents: If supplied (regardless of value), the layer's contents are
          not included in the output.

    Args:
      layer: The layer to represent.
    """
    if self.request.get('id', None) != str(layer.key().id()):
      raise util.BadRequest('Layer IDs do not match in the request.')
    if self.request.get('nocontents', None) is None:
      contents = [(i.key().id(), type(i).__name__)
                  for i in layer.GetSortedContents()]
    else:
      contents = []
    handlers.base.PageHandler.ShowRaw(self, layer, contents=contents)

  def ShowList(self, _):
    """Handler to show a list of all the layers accessible to this user."""
    user = users.get_current_user()
    layer_ids = [layer.key().id() for layer in model.Layer.all()
                 if layer.IsPermitted(user, model.Permission.ACCESS)]
    self.response.out.write(json.dumps(layer_ids))

  def Create(self, _):
    """Creates a new layer.

    POST Args:
      name: The name of the new layer.
      description: A brief description of the layer. Optional.
      custom_kml: Any custom KML to add when serializing the layer. Optional.
      world: The sphere on which the layer lies. One of model.Layer.WORLDS.
      item_type: How the layer's contents' visibility is controlled in the
          list. Must be one of the values of CONTAINER_TYPES, defined in
          model.ContainerModelBase. Optional.
      uncacheable: If True, nothing in the layer is ever cached.
      compressed: Whether the KML for this layers is served zipped in KMZ.
          Defaults to True if not specified.
      auto_managed: A flag indicating whether this is a large layer that should
          be managed automatically. Setting this to true blocks manual editing
          forms.
      dynamic_balloons: A flag indicating whether entities in this layer have
          their balloon contents served dynamically.
      division_size: A soft bound on the maximum number of entities in a single
          division. Leaf divisions may have up to 1.5 time this number. Set but
          has no effect on non-auto-managed layers.
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
    """

    def CreateLayerWithPermissions():
      """Creates a layer with full permissions for the current user."""
      dynamic_balloons = bool(self.request.get('dynamic_balloons'))
      division_size = self.GetArgument('division_size', int)
      division_lod_min = self.GetArgument('division_lod_min', int)
      division_lod_min_fade = self.GetArgument('division_lod_min_fade', int)
      division_lod_max = self.GetArgument('division_lod_max', int)
      division_lod_max_fade = self.GetArgument('division_lod_max_fade', int)
      if self.request.get('compressed', None) is None:
        compressed = True
      else:
        compressed = bool(self.request.get('compressed'))

      layer = model.Layer(name=self.request.get('name', None),
                          description=self.request.get('description', None),
                          custom_kml=self.request.get('custom_kml', None),
                          world=self.request.get('world', None),
                          item_type=self.request.get('item_type', None),
                          uncacheable=bool(self.request.get('uncacheable')),
                          auto_managed=bool(self.request.get('auto_managed')),
                          compressed=compressed,
                          dynamic_balloons=dynamic_balloons,
                          division_size=division_size,
                          division_lod_min=division_lod_min,
                          division_lod_min_fade=division_lod_min_fade,
                          division_lod_max=division_lod_max,
                          division_lod_max_fade=division_lod_max_fade)
      layer.put()
      user = users.get_current_user()
      for permission_type in model.Permission.TYPES:
        model.Permission(layer=layer, user=user, type=permission_type,
                         parent=layer).put()
      return layer.key().id()
    try:
      layer_id = db.run_in_transaction(CreateLayerWithPermissions)
    except (db.BadValueError, TypeError, ValueError), e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(layer_id)

  def Update(self, layer):
    """Updates a layer's properties.

    All POST arguments to this function are optional.

    POST Args:
      Accepts the same POST arguments as Create(), all optional, in addition to:
      icon: The ID of the Resource containing the icon for this layer.

    Args:
      layer: The layer to update.
    """
    if not layer: raise util.BadRequest('Layer required.')

    try:
      for field in ('name', 'description', 'custom_kml', 'world', 'item_type'):
        value = self.request.get(field, None)
        if value == '':  # pylint: disable-msg=C6403
          setattr(layer, field, None)
        elif value is not None:
          setattr(layer, field, value)

      icon = self.request.get('icon', None)
      if not icon and icon is not None:
        layer.icon = None
      elif icon is not None:
        icon = util.GetInstance(model.Resource, icon, layer)
        if icon.type != 'icon':
          raise util.BadRequest('Invalid (non-icon) resource specified.')
        else:
          layer.icon = icon

      bools = ('auto_managed', 'dynamic_balloons', 'compressed', 'uncacheable')
      for arg in bools:
        value = self.request.get(arg, None)
        if value:
          setattr(layer, arg, True)
        elif value is not None:
          setattr(layer, arg, False)

      for arg in ('division_size', 'division_lod_min', 'division_lod_min_fade',
                  'division_lod_max', 'division_lod_max_fade'):
        value = self.request.get(arg, None)
        if value == '':  # pylint: disable-msg=C6403
          setattr(layer, arg, None)
        elif value is not None:
          setattr(layer, arg, int(value))

      layer.ClearCache()
      layer.put()
    except (db.BadValueError, TypeError, ValueError), e:
      raise util.BadRequest(str(e))

  def Delete(self, layer):
    """Deletes the specified layer and all its contents."""
    if not layer: raise util.BadRequest('Layer required.')
    layer.busy = True
    layer.put()
    taskqueue.add(url='/layer-continue-delete/%d' % layer.key().id())


class LayerQueueHandler(handlers.base.PageHandler):
  """A handler to continue layer deletion after timing out."""

  PERMISSION_REQUIRED = None
  REQUIRES_LAYER = False

  def Delete(self, layer):
    """Deletes the specified layer and all its contents."""
    if not layer:
      return

    try:
      self._DeleteAllInQuery(layer.style_set)
      self._DeleteAllInQuery(layer.division_set)
      self._DeleteAllInQuery(layer.folder_set)
      self._DeleteAllInQuery(layer.link_set)
      self._DeleteAllInQuery(layer.region_set)
      self._DeleteAllInQuery(layer.schema_set, model.Schema.SafeDelete)
      self._DeleteAllInQuery(layer.entity_set, model.Entity.SafeDelete)
      for resource in layer.resource_set:
        if resource.blob:
          resource.blob.delete()
        resource.delete()
      layer.SafeDelete()
    except (runtime.DeadlineExceededError, db.Error,
            apiproxy_errors.OverQuotaError):
      # Schedule continuation.
      taskqueue.add(url='/layer-continue-delete/%d' % layer.key().id())

  @staticmethod
  def _DeleteAllInQuery(query, delete_function=None):
    if delete_function is None:
      delete_function = lambda x: x.delete()
    while True:
      objects = query.fetch(1000)
      if not objects:
        return
      for db_object in objects:
        delete_function(db_object)
      query.with_cursor(query.cursor())
