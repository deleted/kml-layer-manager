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

"""Medium tests for the Folder handler."""


import StringIO
from google.appengine import runtime
from google.appengine.api.labs import taskqueue
from handlers import base
from handlers import folder
from lib.mox import mox
import model
import util


class FolderHandlerTest(mox.MoxTestBase):

  def testDeleteSuccess(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = folder.FolderHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_folder = self.mox.CreateMock(model.Folder)
    mock_folder.entity_set = [self.mox.CreateMockAnything() for _ in xrange(3)]
    mock_folder.entity_set[0].folder = object()
    mock_folder.entity_set[1].folder = object()
    mock_folder.entity_set[2].folder = object()
    mock_layer = self.mox.CreateMock(model.Layer)
    dummy_id = object()

    mock_layer.ClearCache()
    handler.request.get('folder_id').AndReturn(dummy_id)
    util.GetInstance(model.Folder, dummy_id, mock_layer).AndReturn(mock_folder)
    for entity in mock_folder.entity_set:
      entity.put()
    mock_folder.delete()

    self.mox.ReplayAll()
    handler.Delete(mock_layer)
    self.assertEqual(mock_folder.entity_set[0].folder, None)
    self.assertEqual(mock_folder.entity_set[1].folder, None)
    self.assertEqual(mock_folder.entity_set[2].folder, None)

  def testDeleteFailure(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = folder.FolderHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMock(model.Layer)
    dummy_id = object()

    mock_layer.ClearCache()
    handler.request.get('folder_id').AndReturn(dummy_id)
    util.GetInstance(model.Folder, dummy_id, mock_layer).AndRaise(
        util.BadRequest)

    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, handler.Delete, mock_layer)

  def testDeleteInterrupt(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(taskqueue, 'add')
    handler = folder.FolderHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.request.path = object()
    mock_folder = self.mox.CreateMockAnything()
    mock_folder.entity_set = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_key = self.mox.CreateMockAnything()
    dummy_id = object()

    mock_layer.ClearCache()
    handler.request.get('folder_id').AndReturn(dummy_id)
    util.GetInstance(model.Folder, dummy_id, mock_layer).AndReturn(mock_folder)
    mock_folder.entity_set.__iter__().AndRaise(runtime.DeadlineExceededError)
    mock_layer.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)
    taskqueue.add(url='/folder-continue-delete/42',
                  params={'folder_id': dummy_id})

    self.mox.ReplayAll()
    handler.Delete(mock_layer)

  def testShowRaw(self):
    self.mox.StubOutWithMock(base.PageHandler, 'ShowRaw')
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = folder.FolderHandler()
    handler.request = self.mox.CreateMockAnything()
    layer = model.Layer(name='a', world='earth')
    layer.put()
    entity = model.Entity(layer=layer, name='x')
    entity_id = entity.put().id()
    link = model.Link(layer=layer, name='y', url='z')
    link_id = link.put().id()
    mock_folder = self.mox.CreateMock(model.Folder)
    self.mox.StubOutWithMock(mock_folder, 'GetSortedContents')
    dummy_id = object()

    handler.request.get('nocontents', None).AndReturn('yes')
    base.PageHandler.ShowRaw(handler, layer, contents=[])

    handler.request.get('nocontents', None).AndReturn(None)
    handler.request.get('id').AndReturn(dummy_id)
    util.GetInstance(model.Folder, dummy_id, layer).AndReturn(mock_folder)
    mock_folder.GetSortedContents().AndReturn(
        [entity, link])
    contents = [(entity_id, 'Entity'), (link_id, 'Link')]
    base.PageHandler.ShowRaw(handler, layer, contents=contents)

    self.mox.ReplayAll()
    # Nocontents set.
    handler.ShowRaw(layer)
    # Nocontents unset.
    handler.ShowRaw(layer)

  def testCreateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    parent_folder = model.Folder(layer=layer, name='c')
    parent_folder_id = parent_folder.put().id()
    region = model.Region(layer=layer, north=1.0, south=0.0, east=1.0, west=0.0)
    region_id = region.put().id()

    handler = folder.FolderHandler()
    handler.request = {
        'name': 'ghi',
        'description': 'jkl',
        'icon': str(icon_id),
        'folder': str(parent_folder_id),
        'folder_index': '42',
        'region': str(region_id),
        'item_type': 'checkHideChildren',
        'custom_kml': 'mno'
    }
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Folder.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'ghi')
    self.assertEqual(result.description, 'jkl')
    self.assertEqual(result.icon.key().id(), icon_id)
    self.assertEqual(result.folder.key().id(), parent_folder_id)
    self.assertEqual(result.folder_index, 42)
    self.assertEqual(result.region.key().id(), region_id)
    self.assertEqual(result.item_type, 'checkHideChildren')
    self.assertEqual(result.custom_kml, 'mno')

  def testCreateMinimalSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()

    handler = folder.FolderHandler()
    handler.request = {'name': 'abc'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Folder.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.description, None)
    self.assertEqual(result.icon, None)
    self.assertEqual(result.folder, None)
    self.assertEqual(result.folder_index, None)
    self.assertEqual(result.region, None)
    self.assertEqual(result.item_type, None)
    self.assertEqual(result.custom_kml, None)

  def testCreateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='a', world='earth')
    other_layer.put()
    bad_folder = model.Folder(layer=other_layer, name='c')
    bad_folder_id = bad_folder.put().id()
    bad_icon = model.Resource(layer=layer, type='image', filename='b')
    bad_icon_id = bad_icon.put().id()

    handler = folder.FolderHandler()

    # Name missing.
    handler.request = {}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid folder ID.
    handler.request = {'name': 'cd', 'folder': '1337'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Foreign parent folder.
    handler.request = {'name': 'cd', 'folder': str(bad_folder_id)}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid parent folder index.
    handler.request = {'name': 'cd', 'folder_index': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Name too long.
    handler.request = {'name': 'cd' * 600}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Non-icon resource for the icon.
    handler.request = {'name': 'cd', 'icon': str(bad_icon_id)}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid item type.
    handler.request = {'name': 'cd', 'item_type': 'x'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

  def testUpdateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon.put()
    parent_folder = model.Folder(layer=layer, name='c')
    parent_folder_id = parent_folder.put().id()
    region = model.Region(layer=layer, north=1.0, south=0.0, east=1.0, west=0.0)
    region.put()
    folder_to_update = model.Folder(layer=layer, name='ghi', description='jkl',
                                    icon=icon, folder=parent_folder,
                                    folder_index=42, region=region,
                                    item_type='checkHideChildren')
    folder_id = folder_to_update.put().id()

    handler = folder.FolderHandler()
    handler.request = {
        'folder_id': str(folder_id),
        'name': 'pqr',
        'description': 'stu',
        'icon': '',
        'folder': str(parent_folder_id),
        'folder_index': '123',
        'region': '',
        'item_type': 'radioFolder',
        'custom_kml': 'vwx'
    }
    handler.Update(layer)
    updated_folder = model.Folder.get_by_id(folder_id)
    self.assertEqual(updated_folder.layer.key().id(), layer_id)
    self.assertEqual(updated_folder.name, 'pqr')
    self.assertEqual(updated_folder.description, 'stu')
    self.assertEqual(updated_folder.icon, None)
    self.assertEqual(updated_folder.folder.key().id(), parent_folder_id)
    self.assertEqual(updated_folder.folder_index, 123)
    self.assertEqual(updated_folder.region, None)
    self.assertEqual(updated_folder.item_type, 'radioFolder')
    self.assertEqual(updated_folder.custom_kml, 'vwx')

  def testUpdateNoOpSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    parent_folder = model.Folder(layer=layer, name='c')
    parent_folder_id = parent_folder.put().id()
    folder_to_update = model.Folder(layer=layer, name='ghi', description='jkl',
                                    icon=icon, folder=parent_folder,
                                    folder_index=42,
                                    item_type='checkHideChildren')
    folder_id = folder_to_update.put().id()

    handler = folder.FolderHandler()
    handler.request = {'folder_id': str(folder_id)}
    handler.Update(layer)
    updated_folder = model.Folder.get_by_id(folder_id)
    self.assertEqual(updated_folder.layer.key().id(), layer_id)
    self.assertEqual(updated_folder.name, 'ghi')
    self.assertEqual(updated_folder.description, 'jkl')
    self.assertEqual(updated_folder.icon.key().id(), icon_id)
    self.assertEqual(updated_folder.folder.key().id(), parent_folder_id)
    self.assertEqual(updated_folder.folder_index, 42)
    self.assertEqual(updated_folder.region, None)
    self.assertEqual(updated_folder.item_type, 'checkHideChildren')
    self.assertEqual(updated_folder.custom_kml, None)

  def testUpdatePartialSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon.put()
    new_icon = model.Resource(layer=layer, type='icon', filename='b2')
    new_icon_id = new_icon.put().id()
    parent_folder = model.Folder(layer=layer, name='c')
    parent_folder_id = parent_folder.put().id()
    folder_to_update = model.Folder(layer=layer, name='ghi', description='jkl',
                                    icon=icon, folder=parent_folder,
                                    folder_index=42,
                                    item_type='checkHideChildren',
                                    custom_kml='mno')
    folder_id = folder_to_update.put().id()

    handler = folder.FolderHandler()
    handler.request = {
        'folder_id': str(folder_id),
        'name': 'new',
        'icon': str(new_icon_id)
    }
    handler.Update(layer)
    updated_folder = model.Folder.get_by_id(folder_id)
    self.assertEqual(updated_folder.layer.key().id(), layer_id)
    self.assertEqual(updated_folder.name, 'new')
    self.assertEqual(updated_folder.description, 'jkl')
    self.assertEqual(updated_folder.icon.key().id(), new_icon_id)
    self.assertEqual(updated_folder.folder.key().id(), parent_folder_id)
    self.assertEqual(updated_folder.folder_index, 42)
    self.assertEqual(updated_folder.region, None)
    self.assertEqual(updated_folder.item_type, 'checkHideChildren')
    self.assertEqual(updated_folder.custom_kml, 'mno')

  def testUpdateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='a', world='earth')
    other_layer.put()
    bad_folder = model.Folder(layer=other_layer, name='c')
    bad_folder_id = bad_folder.put().id()
    bad_icon = model.Resource(layer=layer, type='image', filename='b')
    bad_icon_id = bad_icon.put().id()
    folder_to_update = model.Folder(layer=layer, name='ghi')
    folder_id = folder_to_update.put().id()

    handler = folder.FolderHandler()

    # No folder_id.
    handler.request = {'name': 'abc'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Empty name.
    handler.request = {'folder_id': str(folder_id), 'name': ''}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid parent folder ID.
    handler.request = {'folder_id': str(folder_id), 'folder': '1337'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Foreign parent folder.
    handler.request = {'folder_id': str(folder_id),
                       'folder': str(bad_folder_id)}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid folder index.
    handler.request = {'folder_id': str(folder_id), 'folder_index': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Overly long name.
    handler.request = {'folder_id': str(folder_id), 'name': 'cd' * 600}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Non-icon resource for an icon.
    handler.request = {'folder_id': str(folder_id), 'icon': str(bad_icon_id)}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid item type.
    handler.request = {'folder_id': str(folder_id), 'item_type': 'x'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

  def testMoveSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    folder1 = model.Folder(layer=layer, name='f')
    folder1_id = folder1.put().id()
    folder2 = model.Folder(layer=layer, name='g')
    folder2_id = folder2.put().id()
    parents = [None] * 5 + [folder1] * 5 + [folder2] * 5
    entity_ids = []
    for parent in parents:
      entity = model.Entity(layer=layer, name='e', folder=parent)
      entity_ids.append(entity.put().id())
    handler = folder.FolderHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()

    handler.request.get('parent').AndReturn('')
    handler.request.get_all('contents[]').AndReturn(
        ['entity,%d' % i for i in entity_ids[-2:]])

    handler.request.get('parent').AndReturn(str(folder1_id))
    handler.request.get_all('contents[]').AndReturn(
        ['entity,%d' % i for i in entity_ids[:2] + [entity_ids[10]]])

    handler.request.get('parent').AndReturn(str(folder2_id))
    handler.request.get_all('contents[]').AndReturn(
        ['entity,%d' % i for i in [entity_ids[1]] + entity_ids[4:6]])

    self.mox.ReplayAll()

    handler.response.out = StringIO.StringIO()
    handler.Move(layer)
    self.assertEqual(
        handler.response.out.getvalue(),
        'entity,%d\nentity,%d\n' % (entity_ids[-2], entity_ids[-1]))

    handler.response.out = StringIO.StringIO()
    handler.Move(layer)
    self.assertEqual(handler.response.out.getvalue(),
                     'entity,%d\nentity,%d\nentity,%d\n' %
                     (entity_ids[0], entity_ids[1], entity_ids[10]))

    handler.response.out = StringIO.StringIO()
    handler.Move(layer)
    self.assertEqual(handler.response.out.getvalue(),
                     'entity,%d\nentity,%d\nentity,%d\n' %
                     (entity_ids[1], entity_ids[4], entity_ids[5]))

    expected_parents = [folder1, folder2, None, None, folder2,
                        folder2, folder1, folder1, folder1, folder1,
                        folder1, folder2, folder2, None, None]
    expected_indices = [0, 0, None, None, 1,
                        2, None, None, None, None,
                        2, None, None, 0, 1]
    for i in xrange(15):
      entity = model.Entity.get_by_id(entity_ids[i])
      if expected_parents[i]:
        self.assertEqual(entity.folder.key().id(),
                         expected_parents[i].key().id())
      else:
        self.assertEqual(entity.folder, None)
      self.assertEqual(entity.folder_index, expected_indices[i])

  def testMoveFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    entity = model.Entity(layer=layer, name='e')
    entity_id = entity.put().id()
    handler = folder.FolderHandler()
    handler.request = self.mox.CreateMockAnything()

    # Invalid parent ID.
    handler.request.get('parent').AndReturn('abc')

    # Non-existent parent ID.
    handler.request.get('parent').AndReturn('1337')


    # No contets.
    handler.request.get('parent').AndReturn('')
    handler.request.get_all('contents[]').AndReturn([''])

    # Invalid content type.
    handler.request.get('parent').AndReturn('')
    handler.request.get_all('contents[]').AndReturn(['invalid,%d' % entity_id])

    # Invalid content ID.
    handler.request.get('parent').AndReturn('')
    handler.request.get_all('contents[]').AndReturn(['entity,invalid'])

    # Non-existent content ID.
    handler.request.get('parent').AndReturn('')
    handler.request.get_all('contents[]').AndReturn(['entity,9823746'])

    # Invalid content string format.
    handler.request.get('parent').AndReturn('')
    handler.request.get_all('contents[]').AndReturn(['random'])

    self.mox.ReplayAll()
    for _ in xrange(7):
      self.assertRaises(util.BadRequest, handler.Move, layer)
