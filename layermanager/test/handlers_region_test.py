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

"""Medium tests for the Region handler."""


import StringIO
from handlers import region
from lib.mox import mox
import model
import util


class RegionHandlerTest(mox.MoxTestBase):

  def testDeleteSuccess(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = region.RegionHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_region = self.mox.CreateMock(model.Region)
    mock_region.entity_set = self.mox.CreateMockAnything()
    mock_region.folder_set = self.mox.CreateMockAnything()
    mock_region.link_set = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('region_id').AndReturn(dummy_id)
    util.GetInstance(model.Region, dummy_id, dummy_layer).AndReturn(mock_region)
    mock_region.entity_set.get().AndReturn(None)
    mock_region.folder_set.get().AndReturn(None)
    mock_region.link_set.get().AndReturn(None)
    mock_region.delete()

    self.mox.ReplayAll()
    handler.Delete(dummy_layer)

  def testDeleteFailure(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = region.RegionHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_region = self.mox.CreateMock(model.Region)
    mock_region.entity_set = self.mox.CreateMockAnything()
    mock_region.folder_set = self.mox.CreateMockAnything()
    mock_region.link_set = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('region_id').AndReturn(dummy_id)
    util.GetInstance(model.Region, dummy_id, dummy_layer).AndRaise(
        util.BadRequest)

    handler.request.get('region_id').AndReturn(dummy_id)
    util.GetInstance(model.Region, dummy_id, dummy_layer).AndReturn(mock_region)
    mock_region.entity_set.get().AndReturn(object())

    handler.request.get('region_id').AndReturn(dummy_id)
    util.GetInstance(model.Region, dummy_id, dummy_layer).AndReturn(mock_region)
    mock_region.entity_set.get().AndReturn(None)
    mock_region.folder_set.get().AndReturn(object())

    handler.request.get('region_id').AndReturn(dummy_id)
    util.GetInstance(model.Region, dummy_id, dummy_layer).AndReturn(mock_region)
    mock_region.entity_set.get().AndReturn(None)
    mock_region.folder_set.get().AndReturn(None)
    mock_region.link_set.get().AndReturn(object())

    self.mox.ReplayAll()
    # GetInstance() raises and error.
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)
    # Entities referencing this region exist.
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)
    # Folders referencing this region exist.
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)
    # Links referencing this region exist.
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)

  def testCreateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()

    handler = region.RegionHandler()
    handler.request = {
        'name': 'abc',
        'north': '-40',
        'south': '-50.123',
        'east': '120.0',
        'west': '-190.',
        'min_altitude': '100.0',
        'max_altitude': '200.0',
        'altitude_mode': 'absolute',
        'lod_min': '500',
        'lod_max': '2500',
        'lod_fade_min': '100',
        'lod_fade_max': '50',
    }
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Region.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.north, -40)
    self.assertEqual(result.south, -50.123)
    self.assertEqual(result.east, 120.0)
    self.assertEqual(result.west, -190.)
    self.assertEqual(result.min_altitude, 100.0)
    self.assertEqual(result.max_altitude, 200.0)
    self.assertEqual(result.altitude_mode, 'absolute')
    self.assertEqual(result.lod_min, 500)
    self.assertEqual(result.lod_max, 2500)
    self.assertEqual(result.lod_fade_min, 100)
    self.assertEqual(result.lod_fade_max, 50)

  def testCreateMinimalSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()

    handler = region.RegionHandler()
    handler.request = {'north': '4', 'south': '-3', 'east': '190', 'west': '2'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Region.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, None)
    self.assertEqual(result.north, 4)
    self.assertEqual(result.south, -3)
    self.assertEqual(result.east, 190)
    self.assertEqual(result.west, 2)
    self.assertEqual(result.min_altitude, None)
    self.assertEqual(result.max_altitude, None)
    self.assertEqual(result.altitude_mode, None)
    self.assertEqual(result.lod_min, None)
    self.assertEqual(result.lod_max, None)
    self.assertEqual(result.lod_fade_min, None)
    self.assertEqual(result.lod_fade_max, None)

  def testCreateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    handler = region.RegionHandler()

    handler.request = {}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Missing west.
    handler.request = {'north': '4', 'south': '3', 'east': '2'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # South > North.
    handler.request = {'north': '4', 'south': '5', 'east': '2', 'west': '1'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # West > East.
    handler.request = {'north': '4', 'south': '3', 'east': '1', 'west': '5'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # North > 90.
    handler.request = {'north': '94', 'south': '3', 'east': '2', 'west': '1'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # South < -90.
    handler.request = {'north': '4', 'south': '-96', 'east': '2', 'west': '1'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # LOD Min > LOD Max.
    handler.request = {'north': '4', 'south': '3', 'east': '2', 'west': '1',
                       'lod_min': 100, 'lod_max': 90}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid float.
    handler.request = {'north': '4a', 'south': '3', 'east': '2', 'west': '1'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid integer.
    handler.request = {'north': '4', 'south': '3', 'east': '2', 'west': '1',
                       'lod_min': '1.0'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid altitude mode.
    handler.request = {'north': '4', 'south': '3', 'east': '2', 'west': '1',
                       'altitude_mode': 'foo'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Overly long name.
    handler.request = {'north': '4', 'south': '3', 'east': '2', 'west': '1',
                       'name': 'a' * 999}
    self.assertRaises(util.BadRequest, handler.Create, layer)

  def testUpdateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    region_to_update = model.Region(
        layer=layer, name='ghi', north=4.0, south=3.0, east=2.0, west=1.0,
        min_altitude=50.0, max_altitude=60.0, altitude_mode='absolute',
        lod_min=70, lod_fade_min=80, lod_fade_max=90)
    region_id = region_to_update.put().id()

    handler = region.RegionHandler()
    handler.request = {
        'region_id': region_id,
        'name': 'abc',
        'north': '-40',
        'south': '-50.123',
        'east': '190.0',
        'west': '100.',
        'min_altitude': '100.0',
        'max_altitude': '200.0',
        'altitude_mode': 'clampToGround',
        'lod_min': '500',
        'lod_max': '2500',
        'lod_fade_min': '100',
        'lod_fade_max': '50',
    }
    handler.Update(layer)
    result = model.Region.get_by_id(region_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.north, -40)
    self.assertEqual(result.south, -50.123)
    self.assertEqual(result.east, 190.0)
    self.assertEqual(result.west, 100.)
    self.assertEqual(result.min_altitude, 100.0)
    self.assertEqual(result.max_altitude, 200.0)
    self.assertEqual(result.altitude_mode, 'clampToGround')
    self.assertEqual(result.lod_min, 500)
    self.assertEqual(result.lod_max, 2500)
    self.assertEqual(result.lod_fade_min, 100)
    self.assertEqual(result.lod_fade_max, 50)

  def testUpdateNoOpSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    region_to_update = model.Region(
        layer=layer, name='ghi', north=4.0, south=3.0, east=2.0, west=1.0,
        min_altitude=50.0, max_altitude=60.0, altitude_mode='absolute',
        lod_min=70, lod_fade_min=80, lod_fade_max=90)
    region_id = region_to_update.put().id()

    handler = region.RegionHandler()
    handler.request = {'region_id': region_id}
    handler.Update(layer)
    result = model.Region.get_by_id(region_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'ghi')
    self.assertEqual(result.north, 4)
    self.assertEqual(result.south, 3)
    self.assertEqual(result.east, 2)
    self.assertEqual(result.west, 1)
    self.assertEqual(result.min_altitude, 50.0)
    self.assertEqual(result.max_altitude, 60.0)
    self.assertEqual(result.altitude_mode, 'absolute')
    self.assertEqual(result.lod_min, 70)
    self.assertEqual(result.lod_max, None)
    self.assertEqual(result.lod_fade_min, 80)
    self.assertEqual(result.lod_fade_max, 90)

  def testUpdatePartialSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    region_to_update = model.Region(
        layer=layer, name='ghi', north=4.0, south=3.0, east=2.0, west=1.0,
        min_altitude=50.0, max_altitude=60.0, altitude_mode='absolute',
        lod_min=70, lod_fade_min=80, lod_fade_max=90)
    region_id = region_to_update.put().id()

    handler = region.RegionHandler()
    handler.request = {
        'region_id': region_id,
        'name': 'abc',
        'north': '10',
        'west': '-185',
        'min_altitude': '20.0',
        'lod_min': '2500',
        'lod_fade_max': '150',
    }
    handler.Update(layer)
    result = model.Region.get_by_id(region_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.north, 10)
    self.assertEqual(result.south, 3)
    self.assertEqual(result.east, 2)
    self.assertEqual(result.west, -185.)
    self.assertEqual(result.min_altitude, 20.0)
    self.assertEqual(result.max_altitude, 60.0)
    self.assertEqual(result.altitude_mode, 'absolute')
    self.assertEqual(result.lod_min, 2500)
    self.assertEqual(result.lod_max, None)
    self.assertEqual(result.lod_fade_min, 80)
    self.assertEqual(result.lod_fade_max, 150)

  def testUpdateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    handler = region.RegionHandler()
    region_to_update = model.Region(
        layer=layer, name='ghi', north=4.0, south=3.0, east=2.0, west=1.0,
        min_altitude=50.0, max_altitude=60.0, altitude_mode='absolute',
        lod_min=70, lod_fade_min=80, lod_fade_max=90)
    region_id = region_to_update.put().id()

    handler.request = {}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Missing ID.
    handler.request = {'north': '4', 'south': '3', 'east': '2'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # South > North.
    handler.request = {'region_id': region_id, 'north': '5', 'south': '6'}
    self.assertRaises(util.BadRequest, handler.Update, layer)
    handler.request = {'region_id': region_id, 'north': '2'}
    self.assertRaises(util.BadRequest, handler.Update, layer)
    handler.request = {'region_id': region_id, 'south': '5'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # West > East.
    handler.request = {'region_id': region_id, 'east': '-6', 'west': '-5'}
    self.assertRaises(util.BadRequest, handler.Update, layer)
    handler.request = {'region_id': region_id, 'east': '-5'}
    self.assertRaises(util.BadRequest, handler.Update, layer)
    handler.request = {'region_id': region_id, 'west': '5'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # North > 90.
    handler.request = {'region_id': region_id, 'north': '94'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # North < -90.
    handler.request = {'region_id': region_id, 'north': '-94'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # South > 90.
    handler.request = {'region_id': region_id, 'south': '94'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # South < -90.
    handler.request = {'region_id': region_id, 'south': '-94'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # LOD Min > LOD Max.
    handler.request = {'region_id': region_id, 'lod_min': 90, 'lod_max': 80}
    self.assertRaises(util.BadRequest, handler.Update, layer)
    handler.request = {'region_id': region_id, 'lod_max': 10}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid float.
    handler.request = {'region_id': region_id, 'west': '1a'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid integer.
    handler.request = {'region_id': region_id, 'lod_min': '1.0'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid altitude mode.
    handler.request = {'region_id': region_id, 'altitude_mode': 'foo'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Overly long name.
    handler.request = {'region_id': region_id, 'name': 'a' * 999}
    self.assertRaises(util.BadRequest, handler.Update, layer)
