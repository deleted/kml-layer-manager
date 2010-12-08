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

"""A collection of utility functions and classes."""


import os
import urlparse
from google.appengine.ext import db


class RequestDone(Exception):
  """Signals that the request has been satisfied."""

  def __init__(self, message=None, redirected=False):
    """Initializes the exception, allowing handlers to signal redirection.

    Args:
      message: The error message.
      redirected: Whether the request has been redirected.
    """
    Exception.__init__(self, message)
    self.redirected = redirected


class BadRequest(Exception):
  """Signals that the request was invalid."""
  pass


def GetURL(path):
  """Prepends the protocol and hostname to a URL relative to the root page.

  Args:
    path: The path to append. If it does not begin with a slash, one is
        prepended.

  Returns:
    The full absolute URL.
  """
  if not path.startswith('/'): path = '/' + path
  host = os.environ['SERVER_NAME']
  port = os.environ.get('SERVER_PORT')
  if port and port != '80':
    host += ':%s' % port
  return 'http://' + host + path


def GetInstance(model, instance_id, layer=None, required=True):
  """Tries to get an instance of a model given its ID.

  Args:
    model: The db.Model subclass an instance of which to attempt getting.
    instance_id: The ID of the instance to get.
    layer: The current layer. If not None, makes sure that the instance has a
        layer property equal to this layer.
    required: Whether the instance must be supplied. If false, empty instance_id
        will be considered valid, and result in None returned. Note that even if
        this is set to True, passing an invalid instance_id or one that does not
        belong to the layer (if one is specified) will raise an error.

  Returns:
    The model instance, if successful. If required is False, an empty
    instance_id will result in None returned.

  Raises:
    BadRequest: If a required instance did not exist or the layer did not match.
  """
  if not required and not instance_id:
    return None

  try:
    instance = model.get_by_id(int(instance_id))
  except (ValueError, TypeError, db.BadKeyError):
    instance = None

  if not instance or (layer and instance.layer.key().id() != layer.key().id()):
    raise BadRequest('Invalid %s specified.' % model.__name__.lower())
  else:
    return instance


def GetRequestSourceType(request):
  """Determines how a request was sent. Used for CSRF prevention.

  Args:
    request: The webapp.Request object to analyze.

  Returns:
    A string indicating how the request was sent. One of the following values:
      xhr: Sent from a browser by a JavaScript XMLHttpRequest object.
      api: Sent by the AppEngine RPC API (used by the bulk importer).
      queue: Sent by the AppEngine Queueing mechanism.
      normal: Sent via a normal browser request, referred from the same domain.
      unknown: None of the above.
  """
  if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
    return 'xhr'
  elif request.headers.get('X-AppCfg-API-Version') == '1':
    return 'api'
  elif request.headers.get('X-AppEngine-QueueName'):
    return 'queue'
  else:
    host = urlparse.urlparse(GetURL(''))[1]
    origin = urlparse.urlparse(request.headers.get('Origin', ''))[1]
    if not origin:
      origin = urlparse.urlparse(request.headers.get('Referer', ''))[1]
    if origin == host:
      return 'normal'
    else:
      return 'unknown'
