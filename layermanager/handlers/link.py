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

"""The link editing page of the KML Layer Manager."""

from google.appengine.ext import db
import handlers.base
import handlers.folder
import model
import util


class LinkHandler(handlers.base.PageHandler):
  """A form to create, update and delete links."""

  PERMISSION_REQUIRED = model.Permission.ENTITIES
  FORM_TEMPLATE = 'link'
  ASSOCIATED_MODEL = model.Link

  def Create(self, layer):
    """Creates a new link.

    POST Args:
      Expects POST arguments with the same names as the model.Link properties.
      For reference properties, the expected value is the ID of the referenced
      instance.

    Args:
      layer: The layer to which the new link will belong.
    """
    try:
      fields = handlers.folder.GetContainerFields(self.request, layer)
      url = self.request.get('url', None)
      link = model.Link(layer=layer, url=url, **fields)
      layer.ClearCache()
      link.put()
      link.GenerateKML()  # Build cache.
    except (db.BadValueError, TypeError, ValueError), e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(link.key().id())

  def Update(self, layer):
    """Updates a link's properties.

    POST Args:
      link_id: The ID of the link to update.
      Expects POST arguments with the same names as the model.Link properties.
      For reference properties, the expected value is the ID of the referenced
      instance. All arguments are optional, and those not supplied are left
      untouched.

    Args:
      layer: The layer to which the link to update belongs.
    """
    handlers.folder.UpdateContainer(self.request, layer, 'link_id', model.Link)

  def Delete(self, layer):
    """Deletes a link.

    POST Args:
      link_id: The ID of the link to delete.

    Args:
      layer: The layer to which the link to delete belongs.
    """
    link_id = self.request.get('link_id')
    link = util.GetInstance(model.Link, link_id, layer)
    layer.ClearCache()
    link.delete()
