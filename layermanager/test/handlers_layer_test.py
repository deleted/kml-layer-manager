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

"""Medium tests for the Layer handler."""


import StringIO
from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.api import users
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from handlers import base
from handlers import layer
from lib.mox import mox
import model
import util


class LayerHandlerTest(mox.MoxTestBase):

  def testDelete(self):
    # No layer; fails.
    self.assertRaises(util.BadRequest, layer.LayerHandler().Delete, None)

    # Layer supplied. Succeeds by scheduling a deletion.
    self.mox.StubOutWithMock(taskqueue, 'add')
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_key = self.mox.CreateMockAnything()

    mock_layer.put()
    mock_layer.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)
    taskqueue.add(url='/layer-continue-delete/42')

    self.mox.ReplayAll()
    layer.LayerHandler().Delete(mock_layer)
    self.assertEqual(mock_layer.busy, True)

  def testShowRawFailures(self):
    handler = layer.LayerHandler()
    test_layer = model.Layer(name='a', world='earth')
    layer_id = test_layer.put().id()

    handler.request = {}
    self.assertRaises(util.BadRequest, handler.ShowRaw, test_layer)

    handler.request = {'id': str(1 + layer_id)}
    self.assertRaises(util.BadRequest, handler.ShowRaw, test_layer)

  def testShowRawSuccess(self):
    self.mox.StubOutWithMock(base.PageHandler, 'ShowRaw')
    handler = layer.LayerHandler()
    test_layer = model.Layer(name='a', world='earth')
    self.mox.StubOutWithMock(test_layer, 'GetSortedContents')
    layer_id = test_layer.put().id()
    entity = model.Entity(layer=test_layer, name='x')
    entity_id = entity.put().id()
    link = model.Link(layer=test_layer, name='y', url='z')
    link_id = link.put().id()

    base.PageHandler.ShowRaw(handler, test_layer, contents=[])

    test_layer.GetSortedContents().AndReturn([entity, link])
    contents = [(entity_id, 'Entity'), (link_id, 'Link')]
    base.PageHandler.ShowRaw(handler, test_layer, contents=contents)

    self.mox.ReplayAll()

    # Without contents.
    handler.request = {'id': str(layer_id), 'nocontents': ''}
    handler.ShowRaw(test_layer)

    # With contents.
    handler.request = {'id': str(layer_id)}
    handler.ShowRaw(test_layer)

  def testShowList(self):
    self.mox.StubOutWithMock(users, 'get_current_user')
    self.mox.StubOutWithMock(json, 'dumps')
    self.mox.StubOutWithMock(model.Layer, 'all')
    handler = layer.LayerHandler()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    mock_layers = [self.mox.CreateMock(model.Layer) for _ in xrange(3)]
    mock_keys = [self.mox.CreateMockAnything() for _ in xrange(3)]
    dummy_user = object()
    dummy_result = object()

    users.get_current_user().AndReturn(dummy_user)
    model.Layer.all().AndReturn(mock_layers)
    access_permission = model.Permission.ACCESS
    mock_layers[0].IsPermitted(dummy_user, access_permission).AndReturn(True)
    mock_layers[0].key().AndReturn(mock_keys[0])
    mock_keys[0].id().AndReturn(42)
    mock_layers[1].IsPermitted(dummy_user, access_permission).AndReturn(False)
    mock_layers[2].IsPermitted(dummy_user, access_permission).AndReturn(True)
    mock_layers[2].key().AndReturn(mock_keys[2])
    mock_keys[2].id().AndReturn(13)
    json.dumps([42, 13]).AndReturn(dummy_result)
    handler.response.out.write(dummy_result)

    self.mox.ReplayAll()

    handler.ShowList(None)

  def testCreateCompleteSuccess(self):
    self.stubs.Set(users, 'get_current_user', lambda: users.User('im@test.ing'))
    handler = layer.LayerHandler()
    handler.request = {
        'name': 'abc',
        'description': 'def',
        'custom_kml': 'ghi',
        'world': 'mars',
        'item_type': 'checkHideChildren',
        'auto_managed': '',
        'dynamic_balloons': 'yes',
        'division_size': '123',
        'division_lod_min': '0',
        'division_lod_min_fade': '55',
        'division_lod_max': '789',
        'division_lod_max_fade': '285',
        'compressed': 'true',
        'uncacheable': 'no'
    }
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(None)
    result = model.Layer.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.description, 'def')
    self.assertEqual(result.custom_kml, 'ghi')
    self.assertEqual(result.world, 'mars')
    self.assertEqual(result.item_type, 'checkHideChildren')
    self.assertEqual(result.auto_managed, False)
    self.assertEqual(result.dynamic_balloons, True)
    self.assertEqual(result.compressed, True)
    self.assertEqual(result.uncacheable, True)
    self.assertEqual(result.icon, None)
    self.assertEqual(result.baked, None)
    self.assertEqual(result.division_size, 123)
    self.assertEqual(result.division_lod_min, 0)
    self.assertEqual(result.division_lod_min_fade, 55)
    self.assertEqual(result.division_lod_max, 789)
    self.assertEqual(result.division_lod_max_fade, 285)
    self.assertEqual(result.permission_set.count(999),
                     len(model.Permission.TYPES))
    for permission in result.permission_set:
      self.assertEqual(permission.user.email(), 'im@test.ing')

  def testCreateMinimalSuccess(self):
    self.stubs.Set(users, 'get_current_user', lambda: users.User('im@test.ing'))
    handler = layer.LayerHandler()
    handler.request = {'name': 'abc', 'world': 'earth'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(None)
    result = model.Layer.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.description, None)
    self.assertEqual(result.custom_kml, None)
    self.assertEqual(result.world, 'earth')
    self.assertEqual(result.item_type, None)
    self.assertEqual(result.auto_managed, False)
    self.assertEqual(result.dynamic_balloons, False)
    self.assertEqual(result.compressed, True)
    self.assertEqual(result.uncacheable, False)
    self.assertEqual(result.icon, None)
    self.assertEqual(result.baked, None)
    self.assertEqual(result.division_size, None)
    self.assertEqual(result.division_lod_min, None)
    self.assertEqual(result.division_lod_min_fade, None)
    self.assertEqual(result.division_lod_max, None)
    self.assertEqual(result.division_lod_max_fade, None)
    self.assertEqual(result.permission_set.count(999),
                     len(model.Permission.TYPES))
    for permission in result.permission_set:
      self.assertEqual(permission.user.email(), 'im@test.ing')

  def testCreateInterrupt(self):
    self.mox.StubOutWithMock(users, 'get_current_user')
    handler = layer.LayerHandler()
    handler.request = {'name': 'abc', 'world': 'earth'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    users.get_current_user().AndRaise(db.BadValueError)

    self.mox.ReplayAll()

    self.assertRaises(util.BadRequest, handler.Create, None)
    self.assertEqual(handler.response.out.getvalue(), '')
    self.assertEqual(model.Layer.all().get(), None)
    self.assertEqual(model.Permission.all().get(), None)

  def testCreateFailure(self):
    handler = layer.LayerHandler()

    # No world.
    handler.request = {'name': 'abc'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    # No name.
    handler.request = {'world': 'earth'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    # Empty name.
    handler.request = {'name': '', 'world': 'earth'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    # Overly long name.
    handler.request = {'name': 'a' * 999, 'world': 'earth'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    # Invalid world.
    handler.request = {'name': 'a', 'world': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    # Invalid item type.
    handler.request = {'name': 'a', 'world': 'earth', 'item_type': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    # Invalid integer property.
    handler.request = {'name': 'a', 'world': 'earth', 'division_size': 'a'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    # Float value for integer property.
    handler.request = {'name': 'a', 'world': 'earth', 'division_lod_min': '1.4'}
    self.assertRaises(util.BadRequest, handler.Create, None)

    self.assertEqual(model.Layer.all().get(), None)
    self.assertEqual(model.Permission.all().get(), None)

  def testUpdateCompleteSuccess(self):
    test_layer = model.Layer(name='x', world='earth', description='y',
                             custom_kml='z', item_type='radioFolder',
                             auto_managed=True, dynamic_balloons=False,
                             compressed=True)
    layer_id = test_layer.put().id()
    icon = model.Resource(layer=test_layer, type='icon', filename='b')
    icon_id = icon.put().id()
    handler = layer.LayerHandler()
    handler.request = {
        'name': 'abc',
        'description': 'def',
        'custom_kml': 'ghi',
        'world': 'mars',
        'item_type': 'checkHideChildren',
        'auto_managed': '',
        'dynamic_balloons': 'yes',
        'icon': str(icon_id),
        'division_size': '123',
        'division_lod_min': '456',
        'division_lod_min_fade': '789',
        'division_lod_max': '264',
        'division_lod_max_fade': '0',
        'baked': 'True'  # Shouldn't be settable!
    }
    handler.Update(test_layer)
    updated_layer = model.Layer.get_by_id(layer_id)
    self.assertEqual(updated_layer.name, 'abc')
    self.assertEqual(updated_layer.description, 'def')
    self.assertEqual(updated_layer.custom_kml, 'ghi')
    self.assertEqual(updated_layer.world, 'mars')
    self.assertEqual(updated_layer.item_type, 'checkHideChildren')
    self.assertEqual(updated_layer.auto_managed, False)
    self.assertEqual(updated_layer.dynamic_balloons, True)
    self.assertEqual(updated_layer.compressed, True)
    self.assertEqual(updated_layer.uncacheable, None)
    self.assertEqual(updated_layer.icon.key().id(), icon_id)
    self.assertEqual(updated_layer.baked, None)
    self.assertEqual(updated_layer.division_size, 123)
    self.assertEqual(updated_layer.division_lod_min, 456)
    self.assertEqual(updated_layer.division_lod_min_fade, 789)
    self.assertEqual(updated_layer.division_lod_max, 264)
    self.assertEqual(updated_layer.division_lod_max_fade, 0)

  def testUpdateNoOpSuccess(self):
    test_layer = model.Layer(name='x', world='earth', description='y',
                             custom_kml='z', item_type='radioFolder',
                             auto_managed=True, dynamic_balloons=False,
                             division_size=123, division_lod_min=456,
                             division_lod_max_fade=789, compressed=False,
                             uncacheable=True)
    layer_id = test_layer.put().id()
    handler = layer.LayerHandler()
    handler.request = {}
    handler.Update(test_layer)
    updated_layer = model.Layer.get_by_id(layer_id)
    self.assertEqual(updated_layer.name, 'x')
    self.assertEqual(updated_layer.description, 'y')
    self.assertEqual(updated_layer.custom_kml, 'z')
    self.assertEqual(updated_layer.world, 'earth')
    self.assertEqual(updated_layer.item_type, 'radioFolder')
    self.assertEqual(updated_layer.auto_managed, True)
    self.assertEqual(updated_layer.dynamic_balloons, False)
    self.assertEqual(updated_layer.compressed, False)
    self.assertEqual(updated_layer.uncacheable, True)
    self.assertEqual(updated_layer.icon, None)
    self.assertEqual(updated_layer.baked, None)
    self.assertEqual(updated_layer.division_size, 123)
    self.assertEqual(updated_layer.division_lod_min, 456)
    self.assertEqual(updated_layer.division_lod_min_fade, None)
    self.assertEqual(updated_layer.division_lod_max, None)
    self.assertEqual(updated_layer.division_lod_max_fade, 789)

  def testUpdatePartialSuccess(self):
    test_layer = model.Layer(name='x', world='earth', description='y',
                             custom_kml='z', item_type='radioFolder',
                             auto_managed=True, dynamic_balloons=False,
                             division_size=123, division_lod_min=456,
                             division_lod_min_fade=83)
    layer_id = test_layer.put().id()
    icon = model.Resource(layer=test_layer, type='icon', filename='b')
    icon.put()
    test_layer.icon = icon
    test_layer.put()

    handler = layer.LayerHandler()
    handler.request = {
        'name': 'abc',
        'description': 'def',
        'item_type': 'checkHideChildren',
        'dynamic_balloons': 'yes',
        'icon': '',
        'division_lod_min': '42'
    }
    handler.Update(test_layer)
    updated_layer = model.Layer.get_by_id(layer_id)
    self.assertEqual(updated_layer.name, 'abc')
    self.assertEqual(updated_layer.description, 'def')
    self.assertEqual(updated_layer.custom_kml, 'z')
    self.assertEqual(updated_layer.world, 'earth')
    self.assertEqual(updated_layer.item_type, 'checkHideChildren')
    self.assertEqual(updated_layer.auto_managed, True)
    self.assertEqual(updated_layer.dynamic_balloons, True)
    self.assertEqual(updated_layer.compressed, None)
    self.assertEqual(updated_layer.icon, None)
    self.assertEqual(updated_layer.baked, None)
    self.assertEqual(updated_layer.division_size, 123)
    self.assertEqual(updated_layer.division_lod_min, 42)
    self.assertEqual(updated_layer.division_lod_min_fade, 83)
    self.assertEqual(updated_layer.division_lod_max, None)
    self.assertEqual(updated_layer.division_lod_max_fade, None)

  def testUpdateFailure(self):
    test_layer = model.Layer(name='a', world='earth')
    test_layer.put()
    other_layer = model.Layer(name='b', world='earth')
    other_layer.put()
    bad_icon = model.Resource(layer=test_layer, type='image', filename='b')
    bad_icon_id = bad_icon.put().id()
    foreign_icon = model.Resource(layer=other_layer, type='icon', filename='b')
    foreign_icon_id = foreign_icon.put().id()

    handler = layer.LayerHandler()

    # Empty name.
    handler.request = {'name': ''}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Overly long name.
    handler.request = {'name': 'a' * 999}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Empty world.
    handler.request = {'world': ''}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Invalid world.
    handler.request = {'world': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Invalid item type.
    handler.request = {'item_type': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Invalid integer property.
    handler.request = {'division_size': 'a'}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Float value for integer property.
    handler.request = {'division_lod_min': '1.4'}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Non-icon resource as an icon.
    handler.request = {'icon': bad_icon_id}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)

    # Foreign icon.
    handler.request = {'icon': foreign_icon_id}
    self.assertRaises(util.BadRequest, handler.Update, test_layer)


class LayerDeleteTest(mox.MoxTestBase):

  def testDeleteSuccess(self):
    handler = layer.LayerQueueHandler()
    self.mox.StubOutWithMock(handler, '_DeleteAllInQuery')
    mock_layer = self.mox.CreateMock(model.Layer)
    for set_name in ('style_set', 'division_set', 'folder_set', 'link_set',
                     'region_set', 'entity_set', 'schema_set'):
      setattr(mock_layer, set_name, object())
    mock_layer.resource_set = [self.mox.CreateMockAnything() for _ in xrange(2)]
    mock_layer.resource_set[0].blob = None
    mock_layer.resource_set[1].blob = self.mox.CreateMockAnything()

    handler._DeleteAllInQuery(mock_layer.style_set)
    handler._DeleteAllInQuery(mock_layer.division_set)
    handler._DeleteAllInQuery(mock_layer.folder_set)
    handler._DeleteAllInQuery(mock_layer.link_set)
    handler._DeleteAllInQuery(mock_layer.region_set)
    handler._DeleteAllInQuery(mock_layer.schema_set, model.Schema.SafeDelete)
    handler._DeleteAllInQuery(mock_layer.entity_set, model.Entity.SafeDelete)
    mock_layer.resource_set[0].delete()
    mock_layer.resource_set[1].delete()
    mock_layer.resource_set[1].blob.delete()
    mock_layer.SafeDelete()

    self.mox.ReplayAll()
    handler.Delete(mock_layer)

  def testDeleteInterrupted(self):
    self.mox.StubOutWithMock(taskqueue, 'add')
    handler = layer.LayerQueueHandler()
    self.mox.StubOutWithMock(handler, '_DeleteAllInQuery')
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.style_set = object()
    mock_key = self.mox.CreateMockAnything()

    handler._DeleteAllInQuery(mock_layer.style_set).AndRaise(db.Error)
    mock_layer.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)
    taskqueue.add(url='/layer-continue-delete/42')

    self.mox.ReplayAll()
    handler.Delete(mock_layer)

  def testDeleteRedundantRerun(self):
    self.mox.StubOutWithMock(taskqueue, 'add')  # To make sure it's not called.
    self.mox.ReplayAll()
    layer.LayerQueueHandler().Delete(None)
