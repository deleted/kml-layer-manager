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

"""Custom Django template tags and filters for HTML pages."""


import os
import re
from google.appengine.ext.webapp import template
import settings


register = template.create_template_register()


@register.simple_tag
def InsertJSAPIKey():
  """Returns a Maps JS API key appropriate for the current host."""
  host = os.environ['SERVER_NAME']
  host_and_port = '%s:%s' % (host, os.environ.get('SERVER_PORT', ''))
  return settings.JS_API_KEYS.get(host_and_port,
                                  settings.JS_API_KEYS.get(host, ''))


@register.filter
def EscapeForScriptString(value):
  """Prepends a backslash to the 4 characters: " ' / \ as well as newlines.

  This is used as a template filter to sanitize data for inclusion as Javascript
  strings. This is safer than the existing addslashes filter which allows
  forward slashes and therefore </script> tags.

  Args:
    value: The value to sanitize.

  Returns:
    The sanitized value.
  """
  if value is None:
    return ''
  else:
    intermediate = re.sub(ur'(["/\'\\])', ur'\\\1', u'%s' % value)
    return re.sub(r'(\r|\n|\r\n)', r'\\n', intermediate)


@register.filter
def Lookup(context, key):
  """Performs a standard Django variable resolution.

  Useful for looking up attributes or dictionary items using a key stored in a
  variable.

  Args:
    context: The object whose contents we are looking up.
    key: The name of the key or attribute to look up.

  Returns:
    The lookep up value.
  """
  return template.django.template.resolve_variable(key, context)
