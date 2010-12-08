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

"""Medium tests for the Permission handler."""


from google.appengine.api import users
from google.appengine.ext import db
from handlers import permission
from lib.mox import mox
import model


class PermissionHandlerTest(mox.MoxTestBase):

  def testUpdatePermissions(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='b', world='earth')
    other_layer.put()
    emails = ('foo@example.com', 'bar@baz.net', 'add@me.com', 'add@me.too')
    existing_permissions = (
        ('foo@example.com', model.Permission.ACCESS),
        ('foo@example.com', model.Permission.STYLES),
        ('foo@example.com', model.Permission.ENTITIES),
        ('bar@baz.net', model.Permission.ACCESS),
        ('bar@baz.net', model.Permission.MANAGE),
        ('bar@baz.net', model.Permission.ENTITIES),
        ('bar@baz.net', model.Permission.RESOURCES),
        ('bar@baz.net', model.Permission.STYLES),
        ('bar@baz.net', model.Permission.SCHEMAS),
        ('dont@delete.me', model.Permission.ACCESS),
        ('a@duplicate.i.am', model.Permission.ACCESS),
    )
    new_permissions = (
        ('add@me.com', model.Permission.ACCESS),
        ('add@me.com', model.Permission.RESOURCES),
        ('add@me.too', model.Permission.ACCESS),
        ('add@me.too', model.Permission.MANAGE),
        ('add@me.too', model.Permission.ENTITIES),
        ('add@me.too', model.Permission.RESOURCES),
        ('add@me.too', model.Permission.STYLES),
        ('add@me.too', model.Permission.SCHEMAS),
        ('not@in.emails.list', model.Permission.ACCESS),
        ('not@in.emails.list', model.Permission.ENTITIES),
        ('a@duplicate.i.am', model.Permission.ACCESS),
    )
    expected_results = (
        ('add@me.com', model.Permission.ACCESS),
        ('add@me.com', model.Permission.RESOURCES),
        ('add@me.too', model.Permission.ACCESS),
        ('add@me.too', model.Permission.MANAGE),
        ('add@me.too', model.Permission.ENTITIES),
        ('add@me.too', model.Permission.RESOURCES),
        ('add@me.too', model.Permission.STYLES),
        ('add@me.too', model.Permission.SCHEMAS),
        ('dont@delete.me', model.Permission.ACCESS),
        ('not@in.emails.list', model.Permission.ACCESS),
        ('not@in.emails.list', model.Permission.ENTITIES),
        ('a@duplicate.i.am', model.Permission.ACCESS),
        ('a@duplicate.i.am', model.Permission.ACCESS),  # Twice!
    )

    self.assertEqual(layer.permission_set.get(), None)
    for email, permission_type in existing_permissions:
      model.Permission(user=users.User(email), layer=layer,
                       type=permission_type, parent=layer).put()
      # Also create some decoys.
      model.Permission(user=users.User(email), layer=other_layer,
                       type=permission_type, parent=other_layer).put()
    permissions_to_add = []
    for email, permission_type in new_permissions:
      new = model.Permission(user=users.User(email), layer=layer,
                             type=permission_type, parent=layer)
      permissions_to_add.append(new)

    permission._UpdatePermissions(layer, emails, permissions_to_add)

    self.assertEqual(model.Permission.all().count(999),
                     len(expected_results) + len(existing_permissions))
    self.assertEqual(layer.permission_set.count(999), len(expected_results))
    for email, permission_type in expected_results:
      query = layer.permission_set.filter('user', users.User(email))
      query = query.filter('type', permission_type)
      self.assertTrue(query.get())

  def testShowForm(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='b', world='earth')
    other_layer.put()
    permissions = (
        ('foo@example.com', model.Permission.ACCESS),
        ('foo@example.com', model.Permission.STYLES),
        ('foo@example.com', model.Permission.ENTITIES),
        ('bar@baz.net', model.Permission.ACCESS),
        ('bar@baz.net', model.Permission.MANAGE),
        ('bar@baz.net', model.Permission.ENTITIES),
        ('bar@baz.net', model.Permission.RESOURCES),
        ('bar@baz.net', model.Permission.STYLES),
        ('bar@baz.net', model.Permission.SCHEMAS),
    )
    expected_results = (
        {'email': 'foo@example.com', 'access': True, 'manage': False,
         'entities': True, 'resources': False, 'styles': True,
         'schemas': False},
        {'email': 'bar@baz.net', 'access': True, 'manage': True,
         'entities': True, 'resources': True, 'styles': True, 'schemas': True}
    )

    for email, permission_type in permissions:
      model.Permission(user=users.User(email), layer=layer,
                       type=permission_type, parent=layer).put()
    model.Permission(user=users.User('decoy@example.com'), layer=other_layer,
                     type=model.Permission.ACCESS, parent=other_layer).put()

    handler = permission.PermissionHandler()
    result = handler.ShowForm(layer)
    self.assertEqual(sorted(result.keys()), ['permission_types', 'permissions'])
    self.assertEqual(len(result['permissions']), len(expected_results))
    for record in result['permissions']:
      if record['email'] == 'foo@example.com':
        expected = expected_results[0]
      else:
        expected = expected_results[1]
      self.assertEqual(len(record), len(expected))
      for key in record:
        self.assertEqual(record[key], expected[key])

  def testUpdate(self):
    self.mox.StubOutWithMock(db, 'run_in_transaction')
    handler = permission.PermissionHandler()
    handler.request = self.mox.CreateMockAnything()
    layer = model.Layer(name='a', world='earth')
    layer.put()

    emails = ('foo@example.com', 'bar@baz.net')
    inputs = {
        'foo@example.com_access': '1',
        'foo@example.com_resources': '1',
        'foo@example.com_styles': '1',
        'bar@baz.net_access': '1',
        'bar@baz.net_manage': '1',
        'bar@baz.net_styles': '1',
        'bar@baz.net_resources': '1',
        'bar@baz.net_entities': '1',
        'bar@baz.net_schemas': '1'
    }
    handler.request.get = lambda x: inputs.get(x, '')

    @mox.Func
    def VerifyPermissionsToWrite(permissions):
      for permission in permissions:  # pylint: disable-msg=W0621
        self.assertEqual(permission.layer, layer)
        key = '%s_%s' % (permission.user.email(), permission.type)
        self.assertEqual(inputs[key], '1')
      return True

    handler.request.get_all('users').AndReturn(emails)
    db.run_in_transaction(permission._UpdatePermissions, layer, emails,
                          VerifyPermissionsToWrite)

    self.mox.ReplayAll()
    handler.Update(layer)
