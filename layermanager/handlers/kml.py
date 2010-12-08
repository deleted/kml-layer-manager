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

"""The KML preview page."""

import re
import handlers.base
import model
import util


class KMLFormHandler(handlers.base.PageHandler):
  """A handler to show the KML preview form."""

  PERMISSION_REQUIRED = model.Permission.ACCESS
  FORM_TEMPLATE = 'kml'

  def ShowForm(self, layer):
    """Shows a KML preview and list form."""
    list_url = util.GetURL('/kml-list/%d?with_resources' % layer.key().id())
    return {'kml_list_url': list_url}


class KMLHandler(handlers.base.PageHandler):
  """A handler to generate the KML representation of layers and divisions."""

  PERMISSION_REQUIRED = None
  REQUIRES_LAYER = False

  def ShowList(self, layer):
    """Writes out a list of all the KMLs (and optionally resources) for a layer.

    GET Args:
      with_resources: Whether to include a list of resources.

    Args:
      layer: The layer whose KMLs and resources are to be dumped.
    """
    if not layer: raise util.BadRequest('No valid layer specified.')
    if layer.auto_managed and not layer.baked:
      raise util.BadRequest('This auto-managed layer has not been baked yet.')

    self.response.headers['Content-Type'] = 'text/plain'

    kml_list = _GetKMLURLsList(layer)
    self.response.out.write('\n'.join(kml_list))

    if 'with_resources' in self.request.arguments():
      resources = layer.resource_set.filter('external_url', None)
      resource_urls = []
      for resource in resources:
        url = resource.GetURL(absolute=True)
        if resource.type == 'model_in_kmz':
          # In this context, we want a path to the KMZ, not inside it.
          url = re.sub('\.kmz/.*$', '.kmz', url)
        resource_urls.append(url)
      if resource_urls:
        self.response.out.write('\n' + '\n'.join(resource_urls))


def _GetKMLURLsList(layer, limit=None):
  """Returns a list of all the KMLs for a layer."""
  if layer.compressed:
    extension = 'kmz'
  else:
    extension = 'kml'
  urls = []
  url = util.GetURL('/serve/%d/root.%s' % (layer.key().id(), extension))
  urls.append(url)
  if layer.auto_managed:
    root_division = model.Division.all(keys_only=True).filter('layer', layer)
    root_division = root_division.filter('parent_division', None).get()
    division_keys = model.Division.all(keys_only=True).filter('layer', layer)
    if limit:
      division_keys = division_keys.fetch(limit)
    for division_key in division_keys:
      if division_key != root_division:
        url = util.GetURL('/serve/0/k%d.%s' % (division_key.id(), extension))
        urls.append(url)
  return urls
