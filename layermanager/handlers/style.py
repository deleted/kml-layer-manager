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

"""The styles editing page of the KML Layer Manager."""

from google.appengine.ext import db
import handlers.base
import model
import util


class StyleHandler(handlers.base.PageHandler):
  """A form to create, update and delete styles."""

  PERMISSION_REQUIRED = model.Permission.STYLES
  FORM_TEMPLATE = 'style'
  ASSOCIATED_MODEL = model.Style

  def Create(self, layer):
    """Creates a new style.

    POST Args:
      Expects POST arguments with the same names as the model.Style properties.
      Note: If has_highlight is not supplied or empty, highlight_* properties
      are ignored.

    Args:
      layer: The layer that will contain the new style.
    """
    has_highlight = self.request.get('has_highlight', None)
    # Select the base property names, which we assume to be those for which
    # there is also a corresponding highlight property.
    property_names = [i for i in model.Style.properties()
                      if hasattr(model.Style, 'highlight_' + i)]
    properties = dict([(i, self.request.get(i, None))
                       for i in property_names])
    if has_highlight:
      for property_name in property_names:
        property_name = 'highlight_' + property_name
        properties[property_name] = self.request.get(property_name) or None
    # TODO: Refactor this bit to share with Update().
    for name, value in properties.items():
      property_object = getattr(model.Style, name)
      constructor = property_object.data_type
      try:
        if name.endswith('_color'):
          # Make sure that an empty string for a color is treated as None.
          constructor = lambda x: unicode(x) or None
        elif issubclass(constructor, basestring):
          # Make sure we get a proper unicode string.
          constructor = unicode
        elif constructor is model.Resource:
          # Lookup resource.
          constructor = lambda x: model.Resource.get_by_id(int(x))
          icon = util.GetInstance(model.Resource, value, layer, required=False)
          if icon and icon.type != 'icon':
            raise util.BadRequest('The specified resource must be an icon.')
        if value is not None:
          properties[name] = constructor(value)
      except (TypeError, ValueError):
        raise util.BadRequest('Invalid %s specified.' % name)
    try:
      style = model.Style(layer=layer, name=self.request.get('name', None),
                          has_highlight=bool(has_highlight), **properties)
      style.put()
      style.GenerateKML()  # Build cache.
    except db.BadValueError, e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(style.key().id())

  def Update(self, layer):
    """Updates a style's properties.

    POST Args:
      style_id: The ID of the style to update.
      Also expects the same POST arguments as Create(), all optional.
      Notes:
        1. Supplying a highlight-specific property (e.g. highlight_icon) will
           update it even if the Style's has_highlight property is not True.
        2. Supplying an empty has_highlight in the POST parameters will disable
           style highlight but it will *not* erase highlight properties.

    Args:
      layer: The layer to which the style to update belongs.
    """
    style_id = self.request.get('style_id')
    style = util.GetInstance(model.Style, style_id, layer)
    try:
      for property_name in model.Style.properties():
        value = self.request.get(property_name, None)
        if value == '':  # pylint: disable-msg=C6403
          setattr(style, property_name, None)
        elif value is not None:
          property_object = getattr(model.Style, property_name)
          try:
            constructor = property_object.data_type
            if property_name.endswith('_color'):
              # Make sure that an empty string for a color is treated as None.
              constructor = lambda x: unicode(x) or None
            elif issubclass(constructor, basestring):
              # Make sure we get a proper unicode string.
              constructor = unicode
            elif constructor is model.Resource:
              # Lookup resource.
              constructor = lambda x: model.Resource.get_by_id(int(x))
              icon = util.GetInstance(model.Resource, value, layer,
                                      required=False)
              if icon and icon.type != 'icon':
                raise util.BadRequest('The specified resource must be an icon.')
            value = property_object.validate(constructor(value))
          except (TypeError, ValueError):
            raise util.BadRequest('Invalid %s specified.' % property)
          setattr(style, property_name, value)
      style.ClearCache()
      style.put()
      style.GenerateKML()  # Rebuild cache.
    except db.BadValueError, e:
      raise util.BadRequest(str(e))

  def Delete(self, layer):
    """Deletes a style.

    If any entity references this style, an error is returned.

    POST Args:
      style_id: The ID of the style to delete.

    Args:
      layer: The layer to which the style to delete belongs.
    """
    style_id = self.request.get('style_id')
    style = util.GetInstance(model.Style, style_id, layer)
    if style.entity_set.get():
      raise util.BadRequest('Entities referencing this style exist.')
    style.delete()
