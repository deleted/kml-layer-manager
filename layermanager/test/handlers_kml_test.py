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

"""Small tests for the KML listing handler."""


from handlers import kml
from lib.mox import mox
import model
import util


class KMLHandlerTest(mox.MoxTestBase):

  def testShowListFailures(self):
    handler = kml.KMLHandler()

    self.assertRaises(util.BadRequest, handler.ShowList, None)

    layer = model.Layer(name='a', world='earth', auto_managed=True, baked=False)
    self.assertRaises(util.BadRequest, handler.ShowList, layer)

  def testShowListOfBasicLayer(self):
    self.mox.StubOutWithMock(util, 'GetURL')
    handler = kml.KMLHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.request.arguments = lambda: []
    handler.response = self.mox.CreateMockAnything()
    handler.response.headers = {}
    handler.response.out = self.mox.CreateMockAnything()

    layer = model.Layer(name='a', world='earth', auto_managed=False)
    layer_id = layer.put().id()

    # Uncompressed.
    util.GetURL('/serve/%d/root.kml' % layer_id).AndReturn('dummy')
    handler.response.out.write('dummy')

    # Compressed.
    util.GetURL('/serve/%d/root.kmz' % layer_id).AndReturn('dummy')
    handler.response.out.write('dummy')

    self.mox.ReplayAll()

    handler.ShowList(layer)
    self.assertEqual(handler.response.headers, {'Content-Type': 'text/plain'})

    layer.compressed = True
    handler.ShowList(layer)
    self.assertEqual(handler.response.headers, {'Content-Type': 'text/plain'})

  def testShowListOfBasicLayerWithResources(self):
    self.mox.StubOutWithMock(kml, '_GetKMLURLsList')
    handler = kml.KMLHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.request.arguments = lambda: ['with_resources']
    handler.response = self.mox.CreateMockAnything()
    handler.response.headers = {}
    handler.response.out = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.resource_set = self.mox.CreateMockAnything()
    resources = [self.mox.CreateMockAnything() for _ in xrange(3)]
    resources[1].type = 'model_in_kmz'

    kml._GetKMLURLsList(mock_layer).AndReturn(['xyz'])
    handler.response.out.write('xyz')
    mock_layer.resource_set.filter('external_url', None).AndReturn(resources)
    resources[0].GetURL(absolute=True).AndReturn('abc')
    resources[1].GetURL(absolute=True).AndReturn('def.kmz/ghi')
    resources[2].GetURL(absolute=True).AndReturn('jkl')
    handler.response.out.write('\nabc\ndef.kmz\njkl')

    self.mox.ReplayAll()

    handler.ShowList(mock_layer)
    self.assertEqual(handler.response.headers, {'Content-Type': 'text/plain'})

  def testShowListOfBakedLayer(self):
    self.mox.StubOutWithMock(util, 'GetURL')
    handler = kml.KMLHandler()
    handler.request = self.mox.CreateMockAnything()
    handler.request.arguments = lambda: []
    handler.response = self.mox.CreateMockAnything()
    handler.response.headers = {}
    handler.response.out = self.mox.CreateMockAnything()

    layer = model.Layer(name='a', world='earth', auto_managed=True, baked=True)
    layer_id = layer.put().id()
    divisions = [model.Division(layer=layer, north=1.0, south=0.0,
                                east=1.0, west=0.0, baked=True)
                 for _ in xrange(3)]
    division_ids = [i.put().id() for i in divisions]
    divisions[0].parent_division = divisions[2].parent_division = divisions[1]
    for i in divisions:
      i.put()

    util.GetURL('/serve/%d/root.kml' % layer_id).AndReturn('spam')
    util.GetURL('/serve/0/k%d.kml' % division_ids[0]).AndReturn('eggs')
    util.GetURL('/serve/0/k%d.kml' % division_ids[2]).AndReturn('sausage')
    handler.response.out.write('spam\neggs\nsausage')

    self.mox.ReplayAll()

    handler.ShowList(layer)
    self.assertEqual(handler.response.headers, {'Content-Type': 'text/plain'})
