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

"""A base class for the KML Layer Manager page handlers."""

import collections
import httplib
import os
from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
import model
import settings
import util


class PageHandler(webapp.RequestHandler):
  """An abstract base class for page handlers used to handle common tasks.

  A base class that takes care of operations common to all handlers, such as
  checking permissions, looking up layers and rendering templates.

  Should not be used directly, but rather subclassed by concrete handlers.
  Subclasses should implement methods with the names defined in
  settings.GET_COMMANDS and settings.POST_COMMANDS. These methods are called
  with the current layer object as the sole argument, which may be None if a
  layer ID of 0 is specified in the request. The method should either return
  None to mark the request as finished or a 2-tuple containing a template name
  and a dictionary of template arguments.
  """

  # A constant specifying what permission level the handler requires. Subclasses
  # should override this to specify their own permission requirements.
  PERMISSION_REQUIRED = model.Permission.ACCESS
  # A constant specifying whether a layer must be specified to access this page.
  # Subclasses may override this.
  REQUIRES_LAYER = True
  # A constant specifying what template to evaluate when showing the form for
  # this page. Subclasses should override this.
  FORM_TEMPLATE = 'base'
  # A model class to use when asked to show a raw JSON representation. Should
  # be overriden by subclasses that which to provide raw representations.
  ASSOCIATED_MODEL = None

  def get(self, category, command, layer_id):  # pylint: disable-msg=C6409
    """Verifies the method and forward request to Handle() on success."""
    self.request_type = 'get'
    if command in settings.GET_COMMANDS:
      method = getattr(self, settings.GET_COMMANDS[command])
      self.Handle(category, method, layer_id)
    else:
      self.response.set_status(httplib.METHOD_NOT_ALLOWED)

  def post(self, category, command, layer_id):  # pylint: disable-msg=C6409
    """Verifies the method and forward request to Handle() on success."""
    self.request_type = util.GetRequestSourceType(self.request)
    if self.request_type == 'unknown':
      self.response.set_status(httplib.FORBIDDEN)
    elif command in settings.POST_COMMANDS:
      method = getattr(self, settings.POST_COMMANDS[command])
      self.Handle(category, method, layer_id)
    else:
      self.response.set_status(httplib.METHOD_NOT_ALLOWED)

  def Handle(self, category, method, layer_id):
    """Handles a GET or POST request using the specified method.

    Args:
      category: The category that the current page falls into. Used to determine
          which sidebar link to mark as current.
      method: The function or method to call to handle the request. Usually one
          of the methods defined in *_COMMANDS, bound to the handler.
      layer_id: The ID of the currently selected layer or 0 if no layer is
          selected (e.g. when creating a new layer).
    """
    try:
      layer = self.ValidateLayerAccess(layer_id)
    except util.RequestDone:
      return

    if layer and layer.busy and self.request_type not in ('get', 'queue'):
      self.error(httplib.BAD_REQUEST)
      self.response.out.write('Cannot perform POST requests on a busy layer.')
      return

    self._cache = collections.defaultdict(dict)

    try:
      template_args = method(layer)
    except util.RequestDone, e:
      if e.redirected:
        return
    except util.BadRequest, e:
      self.error(httplib.BAD_REQUEST)
      self.response.out.write(str(e))
      return
    except runtime.DeadlineExceededError:
      self.error(httplib.INTERNAL_SERVER_ERROR)
      self.response.out.write('Operation could not be completed in time.')
      return
    else:
      if template_args is not None:
        self.RenderTemplate(layer, category, self.FORM_TEMPLATE, template_args)

    if self.response.out.len:
      self.response.set_status(httplib.OK)
    else:
      self.response.set_status(httplib.NO_CONTENT)

  def ValidateLayerAccess(self, layer_id):
    """Checks that the user has the required permissions to the specified layer.

    If this is a queue request (and the users API confirms this), all checks
    automatically pass. Likewise if self.PERMISSION_REQUIRED is None.

    Otherwise, verifies that a user is logged in and has the permissions
    specified in self.PERMISSION_REQUIRED to the layer specified by layer_id. If
    self.REQUIRES_LAYER is true, and no layer matching the ID could be found,
    the permissions check is skipped and None is returned (login is still
    checked).

    NOTE: This is the main security gateway for most of the application.

    Args:
      layer_id: The ID of the layer to check access to, either as an integer or
          a string. If None is passed, the layer check is skipped.

    Returns:
      If a layer_id is supplied and all validation is passed, a layer.Layer
      object is returned. If layer_id is 0, self.REQUIRES_LAYER is true and a
      user is logged in, returns None. If validation fails, raises an exception.

    Raises:
      util.RequestDone: Raised if any of the validation steps fail.
    """
    permission = self.PERMISSION_REQUIRED
    user = users.get_current_user()

    if layer_id != 0 and permission is not None:
      if not user:
        self.redirect(users.create_login_url(self.request.path))
        raise util.RequestDone('Redirected to login form.', redirected=True)
      else:
        authenticated = model.AuthenticatedUser.all().filter('user', user).get()
        is_admin = users.is_current_user_admin()
        if settings.USE_GLOBAL_ACL and not (authenticated or is_admin):
          self.error(httplib.FORBIDDEN)
          raise util.RequestDone('Access forbidden.')

    try:
      layer_id = int(layer_id)
    except (TypeError, ValueError):
      self.error(httplib.NOT_FOUND)
      raise util.RequestDone('Invalid layer ID.')

    if layer_id == 0 and not self.REQUIRES_LAYER:
      return None
    else:
      try:
        layer = model.Layer.get_by_id(layer_id)
      except db.BadKeyError:
        layer = None
      if layer is None:
        if self.REQUIRES_LAYER:
          self.error(httplib.NOT_FOUND)
          raise util.RequestDone('Required layer not found.')
        else:
          return None
      elif permission is not None and not layer.IsPermitted(user, permission):
        self.error(httplib.FORBIDDEN)
        raise util.RequestDone('Access forbidden.')
      else:
        return layer

  def RenderTemplate(self, layer, category, name, args):
    """Outputs a template evaluated with the given arguments plus defaults.

    Automatically registers custom_filters.py for the template.

    Args:
      layer: The current layer object.
      category: The category of the page/handler.
      name: The filename of the template, relative to the templates folder.
      args: A dictionary of template arguments used to evaluate the template.
          The following keys have default values that can be overwritten:
            logout_url, username, layer, permissions, all_layers, category
    """
    user = users.get_current_user()
    accessible_layers = _GetAccessibleLayers(user)
    is_debug_server = os.environ['SERVER_SOFTWARE'].startswith('Development')

    permissions = {}
    if layer:
      for permission in layer.permission_set.filter('user', user):
        permissions[permission.type] = True

    actual_args = {'logout_url': users.create_logout_url('/'),
                   'username': user.nickname(),
                   'is_admin': users.is_current_user_admin(),
                   'debug': is_debug_server,
                   'layer': layer,
                   'active_permissions': permissions,
                   'all_layers': accessible_layers,
                   'category': {category or 'home': True}}
    actual_args.update(args)

    template.register_template_library('template_functions.pages')
    template_path = os.path.join(os.path.dirname(__file__), '..',
                                 'html_templates', name + '.html')

    self.response.out.write(template.render(template_path, actual_args))

  def GetArgument(self, name, data_type):
    """Gets a request argument, and typecasts it if not empty."""
    # TODO: Update handlers' code to use this.
    value = self.request.get(name) or None
    if value: value = data_type(value)
    return value

  # Stubs and default implementations for methods to be implemented by
  # subclasses.
  # pylint: disable-msg=W0613
  def ShowForm(self, layer):
    """Handler to render a form page.

    Args:
      layer: The current layer object. None if no layer is currently selected.

    Returns:
      A dictionary of template arguments. An empty one by default, but should be
      overriden by subclasses.
    """
    return {}

  def ShowRaw(self, layer, excludes=(), **extra_data):
    """Handler to show a raw JSON representation of an object.

    GET Args:
      id: The ID of the model instance to lookup.

    Args:
      layer: The current layer object. None if no layer is currently selected.
      excludes: A list of property names to exclude from the output.
      extra_data: Any extra data to include. Used by subclasses that want to use
          this method to serialize their contents. The values are passed to the
          JSON encoder as is, without any processing being applied to them.
    """
    if not self.ASSOCIATED_MODEL:
      raise util.BadRequest('No model associated with this handler.')

    model_class = self.ASSOCIATED_MODEL
    object_id = self.request.get('id')

    if hasattr(model_class, 'layer'):
      instance = util.GetInstance(model_class, object_id, layer)
    elif hasattr(model_class, 'schema'):
      instance = util.GetInstance(model_class, object_id)
      # Verify schema is valid.
      util.GetInstance(model.Schema, instance.schema.key().id(), layer)
    elif model_class is model.Layer:
      instance = layer
    else:
      raise util.BadRequest('Could not match the specified model to a layer.')

    description = {}
    excludes = set(excludes)
    excludes.add('cached_kml')
    # pylint: disable-msg=W0622
    # "property" is a perfect name, and if it shadows a global, so be it.
    for property_name, property in instance.properties().iteritems():
      if property_name in excludes or property_name.endswith('timestamp'):
        continue
      value = getattr(instance, property_name)
      if value is not None:
        if isinstance(property, db.ReferenceProperty):
          value = value.key().id()
        elif isinstance(property, db.GeoPtProperty):
          value = [value.lat, value.lon]
      description[property_name] = value

    for name, value in extra_data.iteritems():
      description[name] = value

    self.response.out.write(json.dumps(description))

  def ShowList(self, layer):
    """Handler to show a list of available instances of the object.

    Args:
      layer: The current layer object. None if no layer is currently selected.
    """
    if not self.ASSOCIATED_MODEL:
      raise util.BadRequest('No model associated with this handler.')

    query = self.ASSOCIATED_MODEL.all(keys_only=True)
    if hasattr(self.ASSOCIATED_MODEL, 'layer'):
      query = query.filter('layer', layer)
    else:
      raise util.BadRequest('No layer directly associated with this model.')

    self.response.out.write(json.dumps([i.id() for i in query]))

  def Create(self, layer):
    """Handler to create an object.

    Args:
      layer: The current layer object. None if no layer is currently selected.
    """
    raise NotImplementedError('Should be implemented by subclasses.')

  def BulkCreate(self, layer):
    """Handler to create a large number of objects at once.

    Args:
      layer: The current layer object. None if no layer is currently selected.
    """
    raise NotImplementedError('Should be implemented by subclasses.')

  def Delete(self, layer):
    """Handler to delete an object.

    Args:
      layer: The current layer object. None if no layer is currently selected.
    """
    raise NotImplementedError('Should be implemented by subclasses.')

  def Update(self, layer):
    """Handler to update an object.

    Args:
      layer: The current layer object. None if no layer is currently selected.
    """
    raise NotImplementedError('Should be implemented by subclasses.')


def MakeStaticHandler(template_name):
  """Create a handler that simply renders a template with default parameters."""

  class StaticHandler(PageHandler):

    def get(self):  # pylint: disable-msg=C6409
      user = users.get_current_user()
      if user:
        authenticated = model.AuthenticatedUser.all().filter('user', user).get()
        is_admin = users.is_current_user_admin()
        if settings.USE_GLOBAL_ACL and not (authenticated or is_admin):
          self.error(httplib.FORBIDDEN)
        else:
          self.RenderTemplate(None, '', template_name, {})
      else:
        self.redirect(users.create_login_url(self.request.path))

  return StaticHandler


def _GetAccessibleLayers(user):
  """Returns the layers accessible to a user.

  Args:
    user: The user whose layers are to be returned.

  Returns:
    A list of Layer objects which the user has access permissions to. Each Layer
    also has an extra managed attribute indicating whether the user has manage
    permissions for that layer.
  """
  accessible_layers = []
  for layer in model.Layer.all():
    if layer.IsPermitted(user, model.Permission.ACCESS):
      layer.managed = layer.IsPermitted(user, model.Permission.MANAGE)
      accessible_layers.append(layer)
  return accessible_layers
