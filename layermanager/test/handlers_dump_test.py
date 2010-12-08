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

"""Small tests for the KML and resource serving handler."""


import httplib
import xml.dom.minidom
import zipfile
from google.appengine.api import images
from google.appengine.ext import blobstore
from handlers import dump
from lib.mox import mox
import model
import settings
import util


class DumpServerTest(mox.MoxTestBase):

  def testGetResource(self):
    handler = dump.DumpServer()
    handler.request = self.mox.CreateMockAnything()
    handler.GetResource = self.mox.CreateMockAnything()
    dummy_id = object()
    dummy_size = object()

    handler.request.get('resize', None).AndReturn(dummy_size)
    handler.request.arguments().AndReturn([])
    handler.GetResource(dummy_id, dummy_size)

    self.mox.ReplayAll()
    handler.get('0', 'r', dummy_id)

  def testGetDivisionKML(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = dump.DumpServer()
    handler.request = self.mox.CreateMockAnything()
    handler.GetKML = self.mox.CreateMockAnything()
    mock_division = self.mox.CreateMockAnything()
    mock_division.layer = self.mox.CreateMockAnything()
    mock_division.layer.compressed = object()
    dummy_id = object()
    dummy_size = object()

    handler.request.get('resize', None).AndReturn(dummy_size)
    handler.request.arguments().AndReturn(['pretty'])
    util.GetInstance(model.Division, dummy_id).AndReturn(mock_division)
    handler.GetKML(mock_division, mock_division.layer.compressed, True)

    self.mox.ReplayAll()
    handler.get('0', 'k', dummy_id)

  def testGetLayerKML(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = dump.DumpServer()
    handler.request = self.mox.CreateMockAnything()
    handler.GetKML = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.auto_managed = False
    mock_layer.compressed = object()
    dummy_layer_id = object()
    dummy_size = object()

    handler.request.get('resize', None).AndReturn(dummy_size)
    handler.request.arguments().AndReturn([])
    util.GetInstance(model.Layer, dummy_layer_id).AndReturn(mock_layer)
    handler.GetKML(mock_layer, mock_layer.compressed, False)

    self.mox.ReplayAll()
    handler.get(dummy_layer_id, None, None)

  def testGetFailsOnUnbakedKML(self):
    handler = dump.DumpServer()
    handler.request = self.mox.CreateMockAnything()
    handler.error = self.mox.CreateMockAnything()
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    layer = model.Layer(name='a', world='earth', auto_managed=True, baked=False)

    handler.request.get('resize', None).AndReturn(None)
    handler.request.arguments().AndReturn([])
    handler.error(httplib.BAD_REQUEST)
    handler.response.out.write('This auto-managed layer has not been baked.')

    self.mox.ReplayAll()
    handler.get(layer.put().id(), None, None)

  def testGetKMLFailsOnMinidomError(self):
    self.mox.StubOutWithMock(xml.dom.minidom, 'parseString')
    handler = dump.DumpServer()
    handler.response = self.mox.CreateMockAnything()
    handler.response.headers = {}
    layer = model.Layer(name='a', world='earth')
    layer.put()

    xml.dom.minidom.parseString(mox.IgnoreArg()).AndRaise(ValueError)

    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, handler.GetKML, layer, False, True)
    self.assertEqual(handler.response.headers,
                     {'Content-Type': settings.KML_MIME_TYPE})

  def testShowRawPrettyLayer(self):
    self.mox.StubOutWithMock(xml.dom.minidom, 'parseString')
    handler = dump.DumpServer()
    handler.response = self.mox.CreateMockAnything()
    handler.response.headers = {}
    handler.response.out = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_xml_tree = self.mox.CreateMockAnything()

    mock_layer.GenerateKML(mox.IgnoreArg()).AndReturn(u'dummy-\u1234')
    xml.dom.minidom.parseString('dummy-\xe1\x88\xb4').AndReturn(mock_xml_tree)
    mock_xml_tree.toprettyxml().AndReturn('a\n\nb\n \t \n\n\nc\nd')
    handler.response.out.write('a\nb\nc\nd')

    self.mox.ReplayAll()
    handler.GetKML(mock_layer, False, True)
    self.assertEqual(handler.response.headers,
                     {'Content-Type': settings.KML_MIME_TYPE})

  def testShowRawCompressedLayer(self):
    self.mox.StubOutWithMock(zipfile, 'ZipFile', use_mock_anything=True)
    handler = dump.DumpServer()
    handler.response = self.mox.CreateMockAnything()
    handler.response.headers = {}
    handler.response.out = object()
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.compressed = True
    mock_zipper = self.mox.CreateMockAnything()

    @mox.Func
    def VerifyZipInfo(zip_info):
      self.assertEqual(zip_info.filename, 'doc.kml')
      self.assertEqual(zip_info.external_attr, 0644 << 16)
      return True

    mock_layer.GenerateKML(mox.IgnoreArg()).AndReturn('a_dummy_string')
    zipfile.ZipFile(
        handler.response.out, 'w', zipfile.ZIP_DEFLATED).AndReturn(mock_zipper)
    mock_zipper.writestr(VerifyZipInfo, 'a_dummy_string')
    mock_zipper.close()

    self.mox.ReplayAll()
    handler.GetKML(mock_layer, True, False)
    self.assertEqual(handler.response.headers,
                     {'Content-Type': settings.KMZ_MIME_TYPE})

  def testGetResourceFailsWithNoResource(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    server = dump.DumpServer()
    dummy_id = object()

    util.GetInstance(model.Resource, dummy_id).AndRaise(util.BadRequest)
    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, server.GetResource, dummy_id)

  def testGetResourceFailsWithNoBlobOrURL(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    server = dump.DumpServer()
    mock_resource = self.mox.CreateMockAnything()
    mock_resource.blob = mock_resource.external_url = None
    dummy_id = object()

    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, server.GetResource, dummy_id)

  def testGetResourceRedirect(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    server = dump.DumpServer()
    server.redirect = self.mox.CreateMockAnything()
    mock_resource = self.mox.CreateMockAnything()
    mock_resource.blob = None
    mock_resource.external_url = object()
    dummy_id = object()

    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    server.redirect(mock_resource.external_url, permanent=True)

    self.mox.ReplayAll()
    server.GetResource(dummy_id)

  def testGetDirectBlobstoreServe(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(blobstore, 'get')
    server = dump.DumpServer()
    server.error = self.mox.CreateMockAnything()
    server.send_blob = self.mox.CreateMockAnything()
    server.response = self.mox.CreateMockAnything()
    server.response.headers = {}
    mock_resource = self.mox.CreateMockAnything()
    mock_resource.blob = self.mox.CreateMockAnything()
    dummy_id = object()
    dummy_key = object()
    cache_headers = {
        'Expires': 'Sat, 19 Jul 2110 22:20:03 +0000',
        'Cache-Control': 'max-age=31557600, public'
    }

    # Simulate blobstore returning failure.
    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    mock_resource.blob.key().AndReturn(dummy_key)
    blobstore.get(dummy_key).AndReturn(None)
    server.error(httplib.NOT_FOUND)

    # Image resource.
    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    mock_resource.blob.key().AndReturn(dummy_key)
    blobstore.get(dummy_key).AndReturn(object())
    server.send_blob(dummy_key)

    # Model resource.
    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    mock_resource.blob.key().AndReturn(dummy_key)
    blobstore.get(dummy_key).AndReturn(object())
    server.send_blob(dummy_key, content_type=settings.COLLADA_MIME_TYPE)

    # Model-in-KMZ resource.
    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    mock_resource.blob.key().AndReturn(dummy_key)
    blobstore.get(dummy_key).AndReturn(object())
    server.send_blob(dummy_key, content_type=settings.KMZ_MIME_TYPE)

    self.mox.ReplayAll()

    server.GetResource(dummy_id)
    self.assertEqual(server.response.headers, {})

    mock_resource.type = 'image'
    server.GetResource(dummy_id)
    self.assertEqual(server.response.headers, cache_headers)

    mock_resource.type = 'model'
    server.GetResource(dummy_id)
    self.assertEqual(server.response.headers, cache_headers)

    mock_resource.type = 'model_in_kmz'
    server.GetResource(dummy_id)
    self.assertEqual(server.response.headers, cache_headers)

  def testGetThumbnail(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(blobstore, 'get')
    self.mox.StubOutWithMock(images, 'Image')
    server = dump.DumpServer()
    server.error = self.mox.CreateMockAnything()
    server.send_blob = self.mox.CreateMockAnything()
    server.response = self.mox.CreateMockAnything()
    server.response.headers = {}
    server.response.out = self.mox.CreateMockAnything()
    mock_resource = self.mox.CreateMockAnything()
    mock_resource.blob = self.mox.CreateMockAnything()
    mock_image = self.mox.CreateMockAnything()
    dummy_id = object()
    dummy_key = object()
    cache_headers = {
        'Expires': 'Sat, 19 Jul 2110 22:20:03 +0000',
        'Cache-Control': 'max-age=31557600, public'
    }

    # Valid size, non-image type.
    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    mock_resource.blob.key().AndReturn(dummy_key)
    blobstore.get(dummy_key).AndReturn(object())
    server.send_blob(dummy_key, content_type=settings.COLLADA_MIME_TYPE)

    # Size equal to the original; execute_transforms() returns an empty string.
    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    mock_resource.blob.key().AndReturn('abc')
    blobstore.get('abc').AndReturn(object())
    images.Image(blob_key='abc').AndReturn(mock_image)
    mock_image.resize(settings.MAX_THUMBNAIL_SIZE, settings.MAX_THUMBNAIL_SIZE)
    mock_image.execute_transforms(output_encoding=images.PNG).AndReturn('')
    server.send_blob('abc')

    # Invalid size, then overly large size.
    for _ in xrange(2):
      util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
      mock_resource.blob.key().AndReturn(dummy_key)
      blobstore.get(dummy_key).AndReturn(object())

    # Valid size and type; generate and write thumbnail.
    util.GetInstance(model.Resource, dummy_id).AndReturn(mock_resource)
    mock_resource.blob.key().AndReturn('abc')
    blobstore.get('abc').AndReturn(object())
    images.Image(blob_key='abc').AndReturn(mock_image)
    mock_image.resize(settings.MAX_THUMBNAIL_SIZE, settings.MAX_THUMBNAIL_SIZE)
    mock_image.execute_transforms(output_encoding=images.PNG).AndReturn('defgh')
    server.response.out.write('defgh')

    self.mox.ReplayAll()

    mock_resource.type = 'model'

    server.GetResource(dummy_id, str(settings.MAX_THUMBNAIL_SIZE))
    self.assertEqual(server.response.headers, cache_headers)
    server.response.headers = {}

    mock_resource.type = 'image'

    server.GetResource(dummy_id, str(settings.MAX_THUMBNAIL_SIZE))
    self.assertEqual(server.response.headers, cache_headers)
    server.response.headers = {}

    self.assertRaises(util.BadRequest, server.GetResource, dummy_id, 'invalid')
    self.assertEqual(server.response.headers, cache_headers)
    server.response.headers = {}

    self.assertRaises(util.BadRequest, server.GetResource,
                      dummy_id, str(settings.MAX_THUMBNAIL_SIZE + 1))
    self.assertEqual(server.response.headers, cache_headers)
    server.response.headers = {}

    server.GetResource(dummy_id, str(settings.MAX_THUMBNAIL_SIZE))
    cache_headers.update({'Content-Type': 'image/png'})
    self.assertEqual(server.response.headers, cache_headers)
