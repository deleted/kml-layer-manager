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

"""Medium tests for the Link handler."""


import StringIO
from handlers import link
from lib.mox import mox
import model
import util


class LinkHandlerTest(mox.MoxTestBase):

  def testDeleteSuccess(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = link.LinkHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_link = self.mox.CreateMock(model.Link)
    mock_layer = self.mox.CreateMockAnything()
    dummy_id = object()

    handler.request.get('link_id').AndReturn(dummy_id)
    util.GetInstance(model.Link, dummy_id, mock_layer).AndReturn(mock_link)
    mock_layer.ClearCache()
    mock_link.delete()

    self.mox.ReplayAll()
    handler.Delete(mock_layer)

  def testDeleteFailure(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = link.LinkHandler()
    handler.request = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('link_id').AndReturn(dummy_id)
    util.GetInstance(model.Link, dummy_id, dummy_layer).AndRaise(
        util.BadRequest)

    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)

  def testCreateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    folder = model.Folder(layer=layer, name='c')
    folder_id = folder.put().id()
    region = model.Region(layer=layer, north=1.0, south=0.0, east=1.0, west=0.0)
    region_id = region.put().id()

    handler = link.LinkHandler()
    handler.request = {
        'url': 'def',
        'name': 'ghi',
        'description': 'jkl',
        'icon': str(icon_id),
        'folder': str(folder_id),
        'folder_index': '42',
        'region': str(region_id),
        'item_type': 'checkHideChildren',
        'custom_kml': 'mno'
    }
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Link.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.url, 'def')
    self.assertEqual(result.name, 'ghi')
    self.assertEqual(result.description, 'jkl')
    self.assertEqual(result.icon.key().id(), icon_id)
    self.assertEqual(result.folder.key().id(), folder_id)
    self.assertEqual(result.folder_index, 42)
    self.assertEqual(result.region.key().id(), region_id)
    self.assertEqual(result.item_type, 'checkHideChildren')
    self.assertEqual(result.custom_kml, 'mno')

  def testCreateMinimalSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()

    handler = link.LinkHandler()
    handler.request = {'url': 'spam', 'name': 'eggs'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Link.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.url, 'spam')
    self.assertEqual(result.name, 'eggs')
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

    handler = link.LinkHandler()

    # No name.
    handler.request = {'url': 'ab'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # No URL.
    handler.request = {'name': 'ab'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid folder.
    handler.request = {'url': 'ab', 'name': 'cd', 'folder': '1337'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Foreign folder.
    handler.request = {'url': 'ab', 'name': 'cd', 'folder': str(bad_folder_id)}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid folder index.
    handler.request = {'url': 'ab', 'name': 'cd', 'folder_index': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Overly long name.
    handler.request = {'url': 'ab', 'name': 'cd' * 600}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Overly long URL.
    handler.request = {'url': 'ab' * 600, 'name': 'cd'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Non-icon resoruce as an icon.
    handler.request = {'url': 'ab', 'name': 'cd', 'icon': str(bad_icon_id)}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid item type.
    handler.request = {'url': 'ab', 'name': 'cd', 'item_type': 'x'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

  def testUpdateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon.put()
    folder = model.Folder(layer=layer, name='c')
    folder_id = folder.put().id()
    region = model.Region(layer=layer, north=1.0, south=0.0, east=1.0, west=0.0)
    region.put()
    link_to_update = model.Link(layer=layer, url='def', name='ghi',
                                description='jkl', icon=icon, folder=folder,
                                folder_index=42, region=region,
                                item_type='checkHideChildren')
    link_id = link_to_update.put().id()

    handler = link.LinkHandler()
    handler.request = {
        'link_id': str(link_id),
        'url': 'mno',
        'name': 'pqr',
        'description': 'stu',
        'icon': '',
        'folder': str(folder_id),
        'folder_index': '123',
        'region': '',
        'item_type': 'radioFolder',
        'custom_kml': 'vwx'
    }
    handler.Update(layer)
    updated_link = model.Link.get_by_id(link_id)
    self.assertEqual(updated_link.layer.key().id(), layer_id)
    self.assertEqual(updated_link.url, 'mno')
    self.assertEqual(updated_link.name, 'pqr')
    self.assertEqual(updated_link.description, 'stu')
    self.assertEqual(updated_link.icon, None)
    self.assertEqual(updated_link.folder.key().id(), folder_id)
    self.assertEqual(updated_link.folder_index, 123)
    self.assertEqual(updated_link.region, None)
    self.assertEqual(updated_link.item_type, 'radioFolder')
    self.assertEqual(updated_link.custom_kml, 'vwx')

  def testUpdateNoOpSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    folder = model.Folder(layer=layer, name='c')
    folder_id = folder.put().id()
    link_to_update = model.Link(layer=layer, url='def', name='ghi',
                                description='jkl', icon=icon, folder=folder,
                                folder_index=42, item_type='checkHideChildren')
    link_id = link_to_update.put().id()

    handler = link.LinkHandler()
    handler.request = {'link_id': str(link_id)}
    handler.Update(layer)
    updated_link = model.Link.get_by_id(link_id)
    self.assertEqual(updated_link.layer.key().id(), layer_id)
    self.assertEqual(updated_link.url, 'def')
    self.assertEqual(updated_link.name, 'ghi')
    self.assertEqual(updated_link.description, 'jkl')
    self.assertEqual(updated_link.icon.key().id(), icon_id)
    self.assertEqual(updated_link.folder.key().id(), folder_id)
    self.assertEqual(updated_link.folder_index, 42)
    self.assertEqual(updated_link.region, None)
    self.assertEqual(updated_link.item_type, 'checkHideChildren')
    self.assertEqual(updated_link.custom_kml, None)

  def testUpdatePartialSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon.put()
    new_icon = model.Resource(layer=layer, type='icon', filename='b2')
    new_icon_id = new_icon.put().id()
    folder = model.Folder(layer=layer, name='c')
    folder_id = folder.put().id()
    link_to_update = model.Link(layer=layer, url='def', name='ghi',
                                description='jkl', icon=icon, folder=folder,
                                folder_index=42, item_type='checkHideChildren',
                                custom_kml='mno')
    link_id = link_to_update.put().id()

    handler = link.LinkHandler()
    handler.request = {
        'link_id': str(link_id),
        'name': 'new',
        'icon': str(new_icon_id)
    }
    handler.Update(layer)
    updated_link = model.Link.get_by_id(link_id)
    self.assertEqual(updated_link.layer.key().id(), layer_id)
    self.assertEqual(updated_link.url, 'def')
    self.assertEqual(updated_link.name, 'new')
    self.assertEqual(updated_link.description, 'jkl')
    self.assertEqual(updated_link.icon.key().id(), new_icon_id)
    self.assertEqual(updated_link.folder.key().id(), folder_id)
    self.assertEqual(updated_link.folder_index, 42)
    self.assertEqual(updated_link.region, None)
    self.assertEqual(updated_link.item_type, 'checkHideChildren')
    self.assertEqual(updated_link.custom_kml, 'mno')

  def testUpdateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='a', world='earth')
    other_layer.put()
    bad_folder = model.Folder(layer=other_layer, name='c')
    bad_folder_id = bad_folder.put().id()
    bad_icon = model.Resource(layer=layer, type='image', filename='b')
    bad_icon_id = bad_icon.put().id()
    link_to_update = model.Link(layer=layer, url='def', name='ghi')
    link_id = link_to_update.put().id()

    handler = link.LinkHandler()

    # No link ID.
    handler.request = {'url': 'abc'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Empty URL.
    handler.request = {'link_id': str(link_id), 'url': ''}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid folder ID.
    handler.request = {'link_id': str(link_id), 'folder': '1337'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Foreign folder.
    handler.request = {'link_id': str(link_id), 'folder': str(bad_folder_id)}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid folder index.
    handler.request = {'link_id': str(link_id), 'folder_index': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Overly long name.
    handler.request = {'link_id': str(link_id), 'name': 'cd' * 600}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Non-icon resource as an icon.
    handler.request = {'link_id': str(link_id), 'icon': str(bad_icon_id)}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid item type.
    handler.request = {'link_id': str(link_id), 'item_type': 'x'}
    self.assertRaises(util.BadRequest, handler.Update, layer)
