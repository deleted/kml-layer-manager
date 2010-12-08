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

"""Small and medium tests for the base request handler."""


import httplib
import os
from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from handlers import base
from lib.mox import mox
import model
import settings
import util


class BaseHandlerTest(mox.MoxTestBase):

  def testGet(self):
    handler = base.PageHandler()
    handler.response = self.mox.CreateMockAnything()
    handler.Handle = self.mox.CreateMockAnything()
    dummy_method = object()
    dummy_category = object()
    dummy_layer_id = object()
    handler.method1 = dummy_method
    self.stubs.Set(settings, 'GET_COMMANDS', {'a': 'method1', 'b': 'method2'})

    handler.Handle(dummy_category, dummy_method, dummy_layer_id)
    handler.response.set_status(httplib.METHOD_NOT_ALLOWED)

    self.mox.ReplayAll()

    # Valid command.
    handler.get(dummy_category, 'a', dummy_layer_id)
    self.assertEqual(handler.request_type, 'get')

    # Invalid command.
    handler.request_type = None
    handler.get(dummy_category, 'x', dummy_layer_id)
    self.assertEqual(handler.request_type, 'get')

  def testPost(self):
    self.mox.StubOutWithMock(util, 'GetRequestSourceType')
    handler = base.PageHandler()
    handler.response = self.mox.CreateMockAnything()
    handler.Handle = self.mox.CreateMockAnything()
    dummy_method = object()
    dummy_category = object()
    dummy_layer_id = object()
    dummy_request = object()
    dummy_request_type = object()
    handler.method1 = dummy_method
    handler.request = dummy_request
    self.stubs.Set(settings, 'POST_COMMANDS', {'a': 'method1', 'b': 'method2'})

    util.GetRequestSourceType(dummy_request).AndReturn('unknown')
    handler.response.set_status(httplib.FORBIDDEN)

    util.GetRequestSourceType(dummy_request).AndReturn(dummy_request_type)
    handler.Handle(dummy_category, dummy_method, dummy_layer_id)

    util.GetRequestSourceType(dummy_request).AndReturn(dummy_request_type)
    handler.response.set_status(httplib.METHOD_NOT_ALLOWED)

    self.mox.ReplayAll()

    # Unknown request type.
    handler.post(dummy_category, 'a', dummy_layer_id)
    self.assertEqual(handler.request_type, 'unknown')

    # Valid request type.
    handler.post(dummy_category, 'a', dummy_layer_id)
    self.assertEqual(handler.request_type, dummy_request_type)

    # Unknown command.
    handler.post(dummy_category, 'x', dummy_layer_id)
    self.assertEqual(handler.request_type, dummy_request_type)

  def testHandleWithInvalidLayer(self):
    handler = base.PageHandler()
    handler.ValidateLayerAccess = self.mox.CreateMockAnything()
    irrelevant = object()
    dummy_layer_id = object()

    handler.ValidateLayerAccess(dummy_layer_id).AndRaise(util.RequestDone)
    self.mox.ReplayAll()
    handler.Handle(irrelevant, irrelevant, dummy_layer_id)

  def testHandleWithBusyLayer(self):
    handler = base.PageHandler()
    handler.error = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    handler.ValidateLayerAccess = self.mox.CreateMockAnything()
    mock_method = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.busy = True
    irrelevant = object()
    dummy_layer_id = object()

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    handler.error(httplib.BAD_REQUEST)
    handler.response.out.write(mox.StrContains('busy'))

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndRaise(util.RequestDone(redirected=True))

    self.mox.ReplayAll()

    # User-initiated; block.
    handler.request_type = 'xhr'
    handler.Handle(irrelevant, irrelevant, dummy_layer_id)
    self.assertFalse(hasattr(handler, '_cache'))

    # Queue-initiated; allow.
    handler.request_type = 'queue'
    handler.Handle(irrelevant, mock_method, dummy_layer_id)
    self.assertTrue(hasattr(handler, '_cache'))

  def testHandleWithMethodRaisingException(self):
    handler = base.PageHandler()
    handler.error = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    handler.ValidateLayerAccess = self.mox.CreateMockAnything()
    mock_method = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.busy = False
    irrelevant = object()
    dummy_layer_id = object()

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndRaise(util.RequestDone(redirected=False))
    handler.response.set_status(httplib.NO_CONTENT)

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndRaise(util.RequestDone(redirected=False))
    handler.response.set_status(httplib.OK)

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndRaise(util.BadRequest('dummy'))
    handler.error(httplib.BAD_REQUEST)
    handler.response.out.write('dummy')

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndRaise(runtime.DeadlineExceededError)
    handler.error(httplib.INTERNAL_SERVER_ERROR)
    handler.response.out.write(mox.StrContains('not be completed in time'))

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndRaise(ValueError)

    self.mox.ReplayAll()

    # Done signal, empty. Set status to NO_CONETNT.
    handler.response.out.len = 0
    handler.Handle(irrelevant, mock_method, dummy_layer_id)
    # Done signal, non-empty. Set status to OK.
    handler.response.out.len = 123
    handler.Handle(irrelevant, mock_method, dummy_layer_id)
    # Bad request exception with an error message.
    handler.Handle(irrelevant, mock_method, dummy_layer_id)
    # Deadline.
    handler.Handle(irrelevant, mock_method, dummy_layer_id)
    # Unexpected exception.
    self.assertRaises(ValueError, handler.Handle,
                      irrelevant, mock_method, dummy_layer_id)

  def testHandleWithSucceedingMethod(self):
    handler = base.PageHandler()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    handler.response.out.len = 0
    handler.ValidateLayerAccess = self.mox.CreateMockAnything()
    handler.RenderTemplate = self.mox.CreateMockAnything()
    mock_method = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.busy = False
    irrelevant = object()
    dummy_category = object()
    dummy_layer_id = object()
    dummy_args = object()
    dummy_template = object()
    handler.FORM_TEMPLATE = dummy_template

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndReturn(None)
    handler.response.set_status(httplib.NO_CONTENT)

    handler.ValidateLayerAccess(dummy_layer_id).AndReturn(mock_layer)
    mock_method(mock_layer).AndReturn(dummy_args)
    handler.RenderTemplate(mock_layer, dummy_category,
                           dummy_template, dummy_args)
    handler.response.set_status(httplib.NO_CONTENT)

    self.mox.ReplayAll()

    # No return.
    handler.Handle(irrelevant, mock_method, dummy_layer_id)
    # Returns args.
    handler.Handle(dummy_category, mock_method, dummy_layer_id)

  def testValidateLayerAccessACLCheck(self):
    model.AuthenticatedUser(user=users.User('test@good.user')).put()

    redirects = []
    errors = []

    handler = base.PageHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.request.path = 'dummy'
    handler.redirect = redirects.append
    handler.error = errors.append
    current_user = None
    is_admin = False
    self.stubs.Set(users, 'get_current_user', lambda: current_user)
    self.stubs.Set(users, 'is_current_user_admin', lambda: is_admin)

    current_user = None
    is_admin = False
    self.assertRaises(util.RequestDone, handler.ValidateLayerAccess, 'x')
    self.assertEqual(len(redirects), 1)
    redirects = []
    self.assertEqual(errors, [])

    current_user = users.User('test@bad.user')
    is_admin = False
    self.assertRaises(util.RequestDone, handler.ValidateLayerAccess, 'x')
    self.assertEqual(redirects, [])
    self.assertEqual(errors, [httplib.FORBIDDEN])
    errors[0:] = []

    current_user = users.User('test@bad.user')
    is_admin = True
    self.assertRaises(util.RequestDone, handler.ValidateLayerAccess, 'x')
    self.assertEqual(redirects, [])
    self.assertEqual(errors, [httplib.NOT_FOUND])
    errors[0:] = []

    current_user = users.User('test@good.user')
    is_admin = False
    self.assertRaises(util.RequestDone, handler.ValidateLayerAccess, 'x')
    self.assertEqual(redirects, [])
    self.assertEqual(errors, [httplib.NOT_FOUND])
    errors[0:] = []

  def testValidateLayerAccessInABlackBox(self):
    anything = object()
    expectations = {
        # Key: permissions, logged in, layer id, layer required.
        # Layer id: 0 -> none; 1 -> exists; 2 -> doesn't exist; x -> bad value.
        (anything, True, 'x', anything): 'not found',
        ('none', False, 'x', anything): 'not found',
        ('valid', False, 'x', anything): 'redirect',
        ('invalid', False, 'x', anything): 'redirect',
        (anything, anything, 0, True): 'not found',
        (anything, anything, 0, False): 'none',
        ('none', anything, 1, anything): 'layer',
        ('valid', True, 1, anything): 'layer',
        ('valid', False, 1, anything): 'redirect',
        ('invalid', True, 1, anything): 'forbidden',
        ('invalid', False, 1, anything): 'redirect',
        ('none', anything, 2, False): 'none',
        ('valid', False, 2, False): 'redirect',
        ('valid', True, 2, False): 'none',
        ('invalid', False, 2, False): 'redirect',
        ('invalid', True, 2, False): 'none',
        (anything, True, 2, True): 'not found',
        ('none', False, 2, True): 'not found',
        ('valid', False, 2, True): 'redirect',
        ('invalid', False, 2, True): 'redirect',
    }

    def ChangeTuple(original, index, value):
      if not 0 <= index < len(original): raise ValueError()
      return original[:index] + (value,) + original[index+1:]

    # Generate full list.
    expanded_expectations = set()
    work_queue = expectations.items()
    while work_queue:
      config, result = work_queue[0]
      work_queue = work_queue[1:]
      (permission, login, layer_id, layer_required) = config

      if permission is anything:
        for permission in ('none', 'valid', 'invalid'):
          work_queue.append((ChangeTuple(config, 0, permission), result))
      elif login is anything:
        for login in (True, False):
          work_queue.append((ChangeTuple(config, 1, login), result))
      elif layer_id is anything:
        for layer_id in (0, 1, 2):
          work_queue.append((ChangeTuple(config, 2, layer_id), result))
      elif layer_required is anything:
        for layer_required in (True, False):
          work_queue.append((ChangeTuple(config, 3, layer_required), result))
      else:
        expanded_expectations.add((config, result))
    self.assertEqual(len(expanded_expectations), 48)  # 3 * 2 * 4 * 2

    # Setup mocks.
    self.stubs.Set(users, 'create_login_url', lambda _: object())
    # Assume that if a user is logged in, they are authenticated. The other case
    # is tested in testValidateLayerAccessACLCheck().
    self.stubs.Set(users, 'is_current_user_admin', lambda: True)
    mock_layer = mox.Mox().CreateMock(model.Layer)  # Skip verification.

    def GetLayer(layer_id):
      if layer_id == 1:
        return mock_layer
      elif layer_id == 0:
        raise db.BadKeyError()
      elif layer_id in (-1, 2):
        return None
      else:
        raise ValueError('Invalid id passed to GetLayer(): %s' % layer_id)
    mock_layer_model = mox.Mox().CreateMockAnything()  # Skip verification.
    mock_layer_model.get_by_id = GetLayer
    self.stubs.Set(model, 'Layer', mock_layer_model)

    # Run tests.
    for config, expected_result in expanded_expectations:
      error_result = []
      message = 'Config: %s / Expected Result: %s' % (config, expected_result)
      handler = base.PageHandler()
      handler.request = mox.Mox().CreateMockAnything()  # Skip verification.
      handler.redirect = lambda _: None
      handler.error = error_result.append

      # Setup inputs.
      (permission, login, layer_id, layer_required) = config
      if permission == 'none':
        handler.PERMISSION_REQUIRED = None
        mock_layer.IsPermitted = lambda _, __: False
      else:
        mock_layer.IsPermitted = lambda _, __: permission == 'valid'
        handler.PERMISSION_REQUIRED = object()
      self.stubs.Set(users, 'get_current_user', lambda: login or None)
      handler.REQUIRES_LAYER = layer_required

      # Make sure old results are always cleared before the check.
      actual_result = object()
      # Check results.
      try:
        actual_result = handler.ValidateLayerAccess(layer_id)
      except util.RequestDone, e:
        if expected_result == 'redirect':
          self.assertTrue(e.redirected, 'Got: %s\n%s' % (e, message))
        elif expected_result == 'forbidden':
          self.assertTrue(not e.redirected,
                          'Got: %s\n%s' % (error_result, message))
          self.assertEqual(error_result, [httplib.FORBIDDEN],
                           'Got: %s\n%s' % (error_result, message))
        elif expected_result == 'not found':
          self.assertTrue(not e.redirected,
                          'Got: %s\n%s' % (error_result, message))
          self.assertEqual(error_result, [httplib.NOT_FOUND],
                           'Got: %s\n%s' % (error_result, message))
        else:
          raise RuntimeError('Unexpected exception raised: %s\n%s\n%s' %
                             (e, error_result, message))
      else:
        if expected_result == 'none':
          self.assertEqual(actual_result, None, message)
        elif expected_result == 'layer':
          self.assertEqual(actual_result, mock_layer, message)
        else:
          raise RuntimeError('Expected test to fail. Got %s instead.\n%s' %
                             (actual_result, message))

  def testRenderTemplate(self):
    self.mox.StubOutWithMock(os.path, 'dirname')
    self.mox.StubOutWithMock(base, '_GetAccessibleLayers')
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.permission_set = self.mox.CreateMockAnything()
    mock_user = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(users, 'get_current_user')
    self.mox.StubOutWithMock(users, 'create_logout_url')
    self.mox.StubOutWithMock(users, 'is_current_user_admin')
    self.mox.StubOutWithMock(template, 'register_template_library')
    self.mox.StubOutWithMock(template, 'render')

    handler = base.PageHandler()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    mock_permissions = [self.mox.CreateMockAnything() for _ in xrange(2)]
    mock_permissions[0].type = 'a'
    mock_permissions[1].type = 'b'
    dummy_category = object()
    dummy_accessible_layers = object()
    dummy_logout_url = object()
    dummy_nickname = object()
    dummy_is_admin = object()
    dummy_result = object()
    name = 'dummy_name'
    args = {'x': 'y', 'z': 'w'}

    @mox.Func
    def VerifyArgs(args):
      expected_args = ['logout_url', 'username', 'is_admin', 'debug', 'layer',
                       'active_permissions', 'all_layers', 'category',
                       'x', 'z']
      self.assertEqual(set(args), set(expected_args))
      self.assertEqual(args['logout_url'], dummy_logout_url)
      self.assertEqual(args['username'], dummy_nickname)
      self.assertEqual(args['is_admin'], dummy_is_admin)
      self.assertEqual(args['debug'], True)
      self.assertEqual(args['layer'], mock_layer)
      self.assertEqual(set(args['active_permissions']), set(['a', 'b']))
      self.assertTrue(args['active_permissions']['a'])
      self.assertTrue(args['active_permissions']['b'])
      self.assertEqual(args['all_layers'], dummy_accessible_layers)
      self.assertEqual(args['category'], {dummy_category: True})
      return True

    users.get_current_user().AndReturn(mock_user)
    base._GetAccessibleLayers(mock_user).AndReturn(dummy_accessible_layers)
    mock_layer.permission_set.filter('user', mock_user).AndReturn(
        mock_permissions)
    users.create_logout_url('/').AndReturn(dummy_logout_url)
    mock_user.nickname().AndReturn(dummy_nickname)
    users.is_current_user_admin().AndReturn(dummy_is_admin)
    template.register_template_library('template_functions.pages')
    os.path.dirname(mox.IgnoreArg()).AndReturn('dummy_dirname')
    template.render('dummy_dirname/../html_templates/dummy_name.html',
                    VerifyArgs).AndReturn(dummy_result)
    handler.response.out.write(dummy_result)

    self.mox.ReplayAll()

    handler.RenderTemplate(mock_layer, dummy_category, name, args)

  def testShowRawFailures(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = base.PageHandler()
    handler.request = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('id').AndReturn(dummy_id)
    handler.request.get('id').AndReturn(dummy_id)
    util.GetInstance(model.Entity, dummy_id, dummy_layer).AndRaise(
        util.BadRequest)

    self.mox.ReplayAll()

    # No associated model.
    self.assertRaises(util.BadRequest, handler.ShowRaw, dummy_layer)

    # Layerless model.
    handler.ASSOCIATED_MODEL = model.Point
    self.assertRaises(util.BadRequest, handler.ShowRaw, dummy_layer)

    # Model with a failing GetInstance().
    handler.ASSOCIATED_MODEL = model.Entity
    self.assertRaises(util.BadRequest, handler.ShowRaw, dummy_layer)

  def testShowRawDefaultRegion(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(json, 'dumps')
    handler = base.PageHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    region = model.Region(layer=layer, name='dummy', lod_fade_max=42,
                          north=1.23, south=4.56, east=7.89, west=-0.12)
    dummy_id = object()
    dummy_result = object()

    util.GetInstance(model.Region, dummy_id, layer).AndReturn(region)
    handler.request.get('id').AndReturn(dummy_id)
    json.dumps({
        'layer': layer_id,
        'name': 'dummy',
        'north': 1.23,
        # Excluding south.
        'east': 7.89,
        'west': -0.12,
        'lod_min': None,
        # Excluding lod_max.
        'lod_fade_min': None,
        'lod_fade_max': 42,
        'min_altitude': None,
        'max_altitude': None,
        'altitude_mode': None,
        'foo': 'bar'  # Extra.
    }).AndReturn(dummy_result)
    handler.response.out.write(dummy_result)

    self.mox.ReplayAll()

    handler.ASSOCIATED_MODEL = model.Region
    handler.ShowRaw(layer, excludes=('lod_max', 'south', 'i_dont_exist'),
                    foo='bar')

  def testShowRawDefaultField(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(json, 'dumps')
    handler = base.PageHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema = model.Schema(layer=layer, name='a')
    schema_id = schema.put().id()
    dummy_id = object()
    dummy_result = object()
    field = model.Field(schema=schema, name='dummy', type='resource')

    handler.request.get('id').AndReturn(dummy_id)
    util.GetInstance(model.Field, dummy_id).AndReturn(field)
    util.GetInstance(model.Schema, schema_id, layer)
    json.dumps({
        'schema': schema_id,
        'name': 'dummy',
        'tip': None,
        'type': 'resource',
    }).AndReturn(dummy_result)
    handler.response.out.write(dummy_result)

    self.mox.ReplayAll()

    handler.ASSOCIATED_MODEL = model.Field
    handler.ShowRaw(layer)

  def testShowRawDefaultEntity(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(json, 'dumps')
    handler = base.PageHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    entity = model.Entity(layer=layer, name='dummy', geometries=[4, 8, 15],
                          view_location=db.GeoPt(12.3, 45.6))
    dummy_id = object()
    dummy_result = object()

    util.GetInstance(model.Entity, dummy_id, layer).AndReturn(entity)
    handler.request.get('id').AndReturn(dummy_id)
    json.dumps({
        'layer': layer_id,
        'name': 'dummy',
        'snippet': None,
        'geometries': [4, 8, 15],
        'folder': None,
        'folder_index': None,
        'style': None,
        'template': None,
        'region': None,
        'view_location': [12.3, 45.6],
        'view_altitude': None,
        'view_heading': None,
        'view_tilt': None,
        'view_roll': None,
        'view_range': None,
        'view_is_camera': None,
        'location': None,
        'location_geocells': [],
        'priority': None,
        'baked': None,
    }).AndReturn(dummy_result)
    handler.response.out.write(dummy_result)

    self.mox.ReplayAll()

    handler.ASSOCIATED_MODEL = model.Entity
    handler.ShowRaw(layer)

  def testShowList(self):
    mock_layer = self.mox.CreateMockAnything()
    handler = base.PageHandler()

    # No associated model.
    handler.ASSOCIATED_MODEL = None
    self.assertRaises(util.BadRequest, handler.ShowList, mock_layer)

    # Layerless model.
    handler.ASSOCIATED_MODEL = self.mox.CreateMock(model.Layer)
    handler.ASSOCIATED_MODEL.all(keys_only=True).AndReturn(object())
    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, handler.ShowList, mock_layer)

    # Valid model with a layer property.
    mock_query = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    handler.ASSOCIATED_MODEL = self.mox.CreateMock(model.Layer)
    handler.ASSOCIATED_MODEL.layer = None

    handler.ASSOCIATED_MODEL.all(keys_only=True).AndReturn(mock_query)
    mock_query.filter('layer', mock_layer).AndReturn(mock_query)
    mock_results = [self.mox.CreateMockAnything() for _ in xrange(2)]
    mock_results[0].id = lambda: 42
    mock_results[1].id = lambda: 666
    mock_query.__iter__().AndReturn((i for i in mock_results))
    handler.response.out.write('[42, 666]')

    self.mox.ReplayAll()
    handler.ShowList(mock_layer)

  def testMakeStaticHandler(self):
    dummy_template = object()
    dummy_path = object()
    dummy_url = object()
    handler_class = base.MakeStaticHandler(dummy_template)
    handler = handler_class()
    handler.request = self.mox.CreateMockAnything()
    handler.request.path = dummy_path
    self.mox.StubOutWithMock(users, 'get_current_user')
    self.mox.StubOutWithMock(users, 'create_login_url')
    self.mox.StubOutWithMock(handler, 'RenderTemplate')
    self.mox.StubOutWithMock(handler, 'redirect')

    # Logged in; render.
    users.get_current_user().AndReturn(True)
    handler.RenderTemplate(None, '', dummy_template, {})

    # Not logged in; redirect.
    users.get_current_user().AndReturn(None)
    users.create_login_url(dummy_path).AndReturn(dummy_url)
    handler.redirect(dummy_url)

    self.mox.ReplayAll()
    handler.get()
    handler.get()

  def testGetAccessibleLayers(self):
    self.mox.StubOutWithMock(model, 'Layer')
    mock_layers = [self.mox.CreateMockAnything() for _ in xrange(3)]
    dummy_user = object()
    permission = model.Permission

    model.Layer.all().AndReturn(mock_layers)
    mock_layers[0].IsPermitted(dummy_user, permission.ACCESS).AndReturn(False)
    mock_layers[1].IsPermitted(dummy_user, permission.ACCESS).AndReturn(True)
    mock_layers[1].IsPermitted(dummy_user, permission.MANAGE).AndReturn(False)
    mock_layers[2].IsPermitted(dummy_user, permission.ACCESS).AndReturn(True)
    mock_layers[2].IsPermitted(dummy_user, permission.MANAGE).AndReturn(True)

    self.mox.ReplayAll()
    self.assertEqual(base._GetAccessibleLayers(dummy_user), mock_layers[1:])
    self.assertEqual(mock_layers[1].managed, False)
    self.assertEqual(mock_layers[2].managed, True)
