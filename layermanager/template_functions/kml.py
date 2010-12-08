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

"""Custom Django template tags and filters for KML documents."""


import cgi
from google.appengine.ext.webapp import template


register = template.create_template_register()


@register.filter
def FormatCoordinates(points, altitudes=None):
  """Formats a list of points into a KML coordinates string.

  Args:
    points: A list of db.GeoPt objects.
    altitudes: An optional list of altitude values. If specified and non-empty,
        must be of the same length as points.

  Returns:
    A string of the specified points in the KML coordinates format.

  Raises:
    ValueError: If the number of the altitudes is not equal to the number of
        points.
  """
  if altitudes:
    if len(points) != len(altitudes):
      raise ValueError('Received %d altitudes. Expected %d.' %
                       (len(altitudes), len(points)))
    coordinates = [(point.lon, point.lat, altitudes[i])
                   for i, point in enumerate(points)]
  else:
    coordinates = [(i.lon, i.lat) for i in points]
  return ' '.join(','.join(str(j) for j in i) for i in coordinates)


@register.filter
def IsNotNone(x):
  return x is not None


@register.filter
def EscapeForXML(text):
  """Escapes the string for safe inclusion as contents of an XML element.

  If the string specified is shorter than 100 bytes in its UTF8 form, all
  ampersands and angle brackets are escaped as XML entities. Otherwise the
  string is wrapped in a CDATA section and all CDATA end markers are properly
  escaped.

  Args:
    text: A freetext unicode or utf8 string of data to escape.

  Returns:
    A string of escaped data encoded as UTF8. If text is falsy, returns an empty
    string.

  Raises:
    TypeError: If a non-string is specified for the text argument.
  """

  if isinstance(text, unicode):
    text = text.encode('utf8')
  elif isinstance(text, str):
    # Validate the text being valid UTF8.
    text.decode('utf8')
  else:
    raise TypeError('Input must be a string.')

  if text:
    if len(text) > 100:
      parts = ('<![CDATA[', text.replace(']]>', ']]]]><![CDATA[>'), ']]>')
      return ''.join(parts)
    else:
      return cgi.escape(text)
  else:
    return ''
