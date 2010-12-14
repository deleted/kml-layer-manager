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

"""The main KML Layer Manager application driver.

Contains a simple main function that starts a WSGI application and defines a
mapping between paths and request handlers.
"""

import os
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
# pylint: disable-msg=C6201
from handlers import (acl, base, dump, entity, folder, kml, layer, link,
                      permission, region, baker, resource, schema, style)

# pylint: disable-msg=C6005
HANDLER_MAP = {
    # Static pages.
    r'/':
      base.MakeStaticHandler('home'),
    r'/earth':
      base.MakeStaticHandler('earth'),
    # Dynamic handlers.
    r'/(baker)-(form|create)/(\d+)':
      baker.Baker,
    r'/(baker)-(update)/(\d+)':
      baker.BakerApprentice,
    r'/(entity)-(form|raw|list|create|bulk|update|delete)/(\d+)':
      entity.EntityHandler,
    r'/(balloon)-(raw)/(\d+)':
      entity.EntityBalloonHandler,
    r'/(field)-(form|raw|list|create|delete)/(\d+)':
      schema.FieldHandler,
    r'/(field-continue)-(delete)/(\d+)?':
      schema.FieldQueueHandler,
    r'/(folder)-(form|raw|list|create|update|move|delete)/(\d+)':
      folder.FolderHandler,
    r'/(folder-continue)-(delete)/(\d+)?':
      folder.FolderQueueHandler,
    r'/(kml)-(form)/(\d+)':
      kml.KMLFormHandler,
    r'/(kml)-(list)/(\d+)':
      kml.KMLHandler,
    r'/(layer)-(form|raw|list|create|update|delete)/(\d+)?':
      layer.LayerHandler,
    r'/(layer-continue)-(delete)/(\d+)?':
      layer.LayerQueueHandler,
    r'/(link)-(form|raw|list|create|update|delete)/(\d+)':
      link.LinkHandler,
    r'/(permission)-(form|update)/(\d+)':
      permission.PermissionHandler,
    r'/(region)-(form|raw|list|create|update|delete)/(\d+)':
      region.RegionHandler,
    r'/(resource)-(form|raw|list|create|bulk|delete)/(\d+)':
      resource.ResourceHandler,
    r'/(schema)-(form|raw|list|create|update|delete)/(\d+)':
      schema.SchemaHandler,
    r'/(style)-(form|raw|list|create|update|delete)/(\d+)':
      style.StyleHandler,
    r'/(template)-(raw|list|create|update|delete)/(\d+)':
      schema.TemplateHandler,
    # Admin-only global permissions editing page. Protected via app.yaml.
    r'/acl':
      acl.ACLHandler,
    # Resource and KML servers. Not using base.BasePageHandler (therefore
    # unprotected). Allows an arbitrary dummy extension to be appended to the
    # URL.
    r'/serve/(\d+)/(?:([kr])(\d+)|root)(?:\.\w+)?':
      dump.DumpServer
}


webapp.template.register_template_library('template_functions.kml_util')
def main():
  debug = os.environ['SERVER_SOFTWARE'].startswith('Development')
  run_wsgi_app(webapp.WSGIApplication(HANDLER_MAP.items(), debug=debug))


if __name__ == '__main__':
  main()
