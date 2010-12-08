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

"""Medium tests for the Resource handler."""


import httplib
import os
import StringIO
from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext import db
from handlers import resource
from lib.mox import mox
import model
import settings
import util


class ResourceHandlerTest(mox.MoxTestBase):

  def testShowForm(self):
    self.mox.StubOutWithMock(blobstore, 'create_upload_url')
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    handler = resource.ResourceHandler()
    dummy_url = object()

    blobstore.create_upload_url('/resource-create/%d' % layer_id).AndReturn(
        dummy_url)

    self.mox.ReplayAll()
    self.assertEqual(handler.ShowForm(layer), {'upload_url': dummy_url})

  def testShowRaw(self):
    self.mox.StubOutWithMock(blobstore, 'create_upload_url')
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    handler = resource.ResourceHandler()
    handler.response = self.mox.CreateMockAnything()

    blobstore.create_upload_url('/resource-create/%d' % layer_id).AndReturn(
        'Escape <me>!')
    blobstore.create_upload_url('/resource-bulk/%d' % layer_id).AndReturn(
        'abc')
    handler.response.set_status(httplib.BAD_REQUEST)

    blobstore.create_upload_url('/resource-create/%d' % layer_id).AndReturn('q')
    blobstore.create_upload_url('/resource-bulk/%d' % layer_id).AndReturn('w')
    handler.response.set_status(httplib.OK)

    self.mox.ReplayAll()

    # Error specified.
    handler.request = {'error': 'abc'}
    handler.response.out = StringIO.StringIO()
    handler.ShowRaw(layer)
    self.assertEqual(handler.response.out.getvalue(),
                     '%d\n\nabc\nEscape &lt;me&gt;!\nabc' % httplib.BAD_REQUEST)

    # Result specified.
    handler.request = {'result': 'def'}
    handler.response.out = StringIO.StringIO()
    handler.ShowRaw(layer)
    self.assertEqual(handler.response.out.getvalue(),
                     '%d\ndef\n\nq\nw' % httplib.OK)

  def testShowList(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='a', world='earth')
    other_layer.put()
    resource1_id = model.Resource(layer=layer, filename='a', type='icon',
                                  external_url='a-url').put().id()
    resource2_id = model.Resource(layer=layer, filename='b', type='icon',
                                  external_url='b-url').put().id()
    model.Resource(layer=other_layer, filename='c', type='image',
                   external_url='c-url').put()
    resource3_id = model.Resource(layer=layer, filename='d', type='image',
                                  external_url='d-url').put().id()
    handler = resource.ResourceHandler()
    handler.response = self.mox.CreateMockAnything()

    # Invalid resource type.
    handler.request = {'type': 'invalid'}
    handler.response.out = StringIO.StringIO()
    self.assertRaises(util.BadRequest, handler.ShowList, layer)
    self.assertEqual(handler.response.out.getvalue(), '')

    # All resources.
    handler.request = {}
    handler.response.out = StringIO.StringIO()
    handler.ShowList(layer)
    result = json.loads(handler.response.out.getvalue())
    self.assertEqual(len(result), 3)
    self.assertTrue({'id': resource1_id, 'name': 'a',
                     'type': 'icon', 'url': 'a-url'} in result)
    self.assertTrue({'id': resource2_id, 'name': 'b',
                     'type': 'icon', 'url': 'b-url'} in result)
    self.assertTrue({'id': resource3_id, 'name': 'd',
                     'type': 'image', 'url': 'd-url'} in result)

    # Icon resources.
    handler.request = {'type': 'icon'}
    handler.response.out = StringIO.StringIO()
    handler.ShowList(layer)
    result = json.loads(handler.response.out.getvalue())
    self.assertEqual(len(result), 2)
    self.assertTrue({'id': resource1_id, 'name': 'a', 'url': 'a-url'} in result)
    self.assertTrue({'id': resource2_id, 'name': 'b', 'url': 'b-url'} in result)

    # Model resources (none).
    handler.request = {'type': 'model'}
    handler.response.out = StringIO.StringIO()
    handler.ShowList(layer)
    self.assertEqual(handler.response.out.getvalue(), '[]')

  def testDeleteSuccess(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(resource, '_IsResourceReferenced')
    handler = resource.ResourceHandler()
    dummy_id = object()
    handler.request = {'resource_id': dummy_id}
    mock_resource1 = self.mox.CreateMock(model.Resource)
    mock_resource1.blob = None
    mock_resource2 = self.mox.CreateMock(model.Resource)
    mock_resource2.blob = self.mox.CreateMockAnything()
    dummy_layer = object()

    util.GetInstance(model.Resource, dummy_id, dummy_layer).AndReturn(
        mock_resource1)
    resource._IsResourceReferenced(mock_resource1).AndReturn(False)
    mock_resource1.delete()

    util.GetInstance(model.Resource, dummy_id, dummy_layer).AndReturn(
        mock_resource2)
    resource._IsResourceReferenced(mock_resource2).AndReturn(False)
    mock_resource2.delete()
    mock_resource2.blob.delete()

    self.mox.ReplayAll()
    # Blobless resource.
    handler.Delete(dummy_layer)
    # Blobful resource.
    handler.Delete(dummy_layer)

  def testDeleteFailure(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(resource, '_IsResourceReferenced')
    handler = resource.ResourceHandler()
    dummy_id = object()
    handler.request = {'resource_id': dummy_id}
    mock_resource = self.mox.CreateMock(model.Resource)
    dummy_layer = object()

    util.GetInstance(model.Resource, dummy_id, dummy_layer).AndRaise(
        util.BadRequest)

    util.GetInstance(model.Resource, dummy_id, dummy_layer).AndReturn(
        mock_resource)
    resource._IsResourceReferenced(mock_resource).AndReturn(True)

    self.mox.ReplayAll()
    # GetInstance() returns None.
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)
    # _IsResourceReferenced() returns True.
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)

  def testCreate(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    handler = resource.ResourceHandler()
    handler._CreateResource = self.mox.CreateMockAnything()
    handler._DeleteBlobs = self.mox.CreateMockAnything()
    handler.redirect = self.mox.CreateMockAnything()
    handler.get_uploads = self.mox.CreateMockAnything()
    dummy_uploads = object()

    handler.get_uploads('file').AndReturn(['def'])
    handler._CreateResource(layer, 'a', 'b', 'c', 'def').AndRaise(
        util.BadRequest('dummy_error'))
    handler.get_uploads().AndReturn(dummy_uploads)
    handler._DeleteBlobs(dummy_uploads)
    handler.redirect('/resource-raw/%d?error=dummy_error' % layer_id)

    handler.get_uploads('file').AndReturn(['hij'])
    handler._CreateResource(layer, 'e', 'f', 'g', 'hij').AndReturn(42)
    handler.redirect('/resource-raw/%d?result=42' % layer_id)

    self.mox.ReplayAll()

    # Simulate _CreateResource() failing.
    handler.request = {'type': 'a', 'filename': 'b', 'url': 'c'}
    try:
      handler.Create(layer)
    except util.RequestDone, e:
      self.assertTrue(e.redirected)
    else:
      self.assertTrue(False, 'Create() did not raise a RequestDone exception.')

    # Simulate _CreateResource() succeeding.
    handler.request = {'type': 'e', 'filename': 'f', 'url': 'g'}
    try:
      handler.Create(layer)
    except util.RequestDone, e:
      self.assertTrue(e.redirected)
    else:
      self.assertTrue(False, 'Create() did not raise a RequestDone exception.')

  def testDeleteBlobs(self):
    mock_blobs = [self.mox.CreateMockAnything() for _ in xrange(3)]

    class DummyError(StandardError):
      pass

    mock_blobs[0].delete()
    mock_blobs[1].delete()
    mock_blobs[2].delete()

    mock_blobs[0].delete().AndRaise(DummyError)

    mock_blobs[0].delete().AndRaise(DummyError)

    self.mox.ReplayAll()

    # Success.
    resource.ResourceHandler._DeleteBlobs(mock_blobs)

    # Failure on dev.
    self.stubs.Set(os, 'environ', {'SERVER_SOFTWARE': 'Development Server'})
    resource.ResourceHandler._DeleteBlobs(mock_blobs)

    # Failure on prod.
    self.stubs.Set(os, 'environ', {'SERVER_SOFTWARE': 'Real Server'})
    self.assertRaises(
        DummyError, resource.ResourceHandler._DeleteBlobs, mock_blobs)

  def testBulkCreate(self):
    uploads = {'file0': object(), 'file2': object()}
    request = {'type0': 'icon', 'type1': 'image', 'type2': 'model',
               'filename0': 'ab', 'filename1': 'def', 'filename2': 'g',
               'url1': 'hij'}
    creations, redirects, deletions = [], [], []

    def DummyGetUploads(name=None):
      if name is None:
        return uploads.values()
      else:
        return [uploads.get(name)]

    def DummyCreateResource(*args):
      creations.append(args)
      return hash(args[1])

    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    handler = resource.ResourceHandler()
    handler.request = request
    handler.get_uploads = DummyGetUploads
    handler._CreateResource = DummyCreateResource
    handler._DeleteBlobs = deletions.extend
    handler.redirect = redirects.append

    # Success.
    try:
      handler.BulkCreate(layer)
    except util.RequestDone, e:
      self.assertTrue(e.redirected)
    else:
      self.assertTrue(False, 'Create() did not raise a RequestDone exception.')
    self.assertEqual(creations, [(layer, 'icon', 'ab', None, uploads['file0']),
                                 (layer, 'image', 'def', 'hij', None),
                                 (layer, 'model', 'g', None, uploads['file2'])])
    args = (layer_id, hash('icon'), hash('image'), hash('model'))
    self.assertEqual(redirects, ['/resource-raw/%s?result=%s,%s,%s' % args])
    self.assertEqual(deletions, [])

    # Invalid input.
    def DummyRaiseInputError(*args):
      if args[1] == 'image': raise util.BadRequest('dummy')
      creations.append(args)
      return hash(args[1])
    handler._CreateResource = DummyRaiseInputError
    for output_container in (creations, redirects, deletions):
      output_container.__delslice__(0, 999)
    try:
      handler.BulkCreate(layer)
    except util.RequestDone, e:
      self.assertTrue(e.redirected)
    else:
      self.assertTrue(False, 'Create() did not raise a RequestDone exception.')
    self.assertEqual(creations, [(layer, 'icon', 'ab', None, uploads['file0'])])
    args = (layer_id, hash('icon'), 'Resource%201%3A%20dummy')
    self.assertEqual(redirects, ['/resource-raw/%s?result=%s&error=%s' % args])
    self.assertEqual(deletions, [uploads['file2']])

    # Deadline.
    def DummyRaiseDeadlineError(*args):
      if args[1] == 'image': raise runtime.DeadlineExceededError('dummy')
      creations.append(args)
      return hash(args[1])
    handler._CreateResource = DummyRaiseDeadlineError
    for output_container in (creations, redirects, deletions):
      output_container.__delslice__(0, 999)
    try:
      handler.BulkCreate(layer)
    except util.RequestDone, e:
      self.assertTrue(e.redirected)
    else:
      self.assertTrue(False, 'Create() did not raise a RequestDone exception.')
    self.assertEqual(creations, [(layer, 'icon', 'ab', None, uploads['file0'])])
    args = (layer_id, hash('icon'), 'Ran%20out%20of%20time.')
    self.assertEqual(redirects, ['/resource-raw/%s?result=%s&error=%s' % args])
    self.assertEqual(deletions, [uploads['file2']])

  def testCreateResource(self):
    create = resource.ResourceHandler._CreateResource
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()

    # Neither URL nor blob.
    self.assertRaises(util.BadRequest, create, layer, 'icon', 'abc', None, None)

    # Non-image blob.
    self.stubs.Set(resource, '_IsImage', lambda _: False)
    self.assertRaises(util.BadRequest, create, layer,
                      'image', 'abc', None, object())

    # Overly large image blob.
    self.stubs.Set(resource, '_IsImage', lambda _: True)
    self.stubs.Set(resource, '_TryGetImageSize',
                   lambda _: (settings.MAX_ICON_SIZE + 1,) * 2)
    self.assertRaises(util.BadRequest, create, layer,
                      'icon', 'abc', None, object())

    # Image blob of unknown size.
    self.stubs.Set(resource, '_IsImage', lambda _: True)
    self.stubs.Set(resource, '_TryGetImageSize', lambda _: None)
    self.assertRaises(util.BadRequest, create, layer,
                      'icon', 'abc', None, object())

    # Valid URL.
    resource_id = create(layer, 'icon', 'def', 'ghi', None)
    result = model.Resource.get_by_id(resource_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.type, 'icon')
    self.assertEqual(result.filename, 'def')
    self.assertEqual(result.external_url, 'ghi')
    self.assertEqual(result.blob, None)

    # Valid blob.
    mock_blob = self.mox.CreateMock(blobstore.BlobInfo)
    mock_blob.key().AndReturn(self.mox.CreateMock(blobstore.BlobKey))
    self.mox.ReplayAll()
    self.stubs.Set(resource, '_IsImage', lambda _: True)
    self.stubs.Set(resource, '_TryGetImageSize',
                   lambda _: (settings.MAX_ICON_SIZE - 1,) * 2)
    resource_id = create(layer, 'icon', 'def', None, mock_blob)
    result = model.Resource.get_by_id(resource_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.type, 'icon')
    self.assertEqual(result.filename, 'def')
    self.assertEqual(result.external_url, None)
    self.assertTrue(result.blob)  # We get *something* back.


class ResourceUtilTest(mox.MoxTestBase):

  def testIsImage(self):
    self.mox.StubOutWithMock(images, 'Image')
    mock_blob = self.mox.CreateMockAnything()
    mock_image = self.mox.CreateMockAnything()

    mock_blob.key().AndReturn('a')
    images.Image(blob_key='a').AndReturn(mock_image)
    mock_image.horizontal_flip()
    mock_image.execute_transforms()

    mock_blob.key().AndReturn('b')
    images.Image(blob_key='b').AndReturn(mock_image)
    mock_image.horizontal_flip()
    mock_image.execute_transforms().AndRaise(images.LargeImageError)

    mock_blob.key().AndReturn('c')
    images.Image(blob_key='c').AndReturn(mock_image)
    mock_image.horizontal_flip()
    mock_image.execute_transforms().AndRaise(images.BadImageError)

    self.mox.ReplayAll()
    self.assertTrue(resource._IsImage(mock_blob))  # Normal success.
    self.assertTrue(resource._IsImage(mock_blob))  # Image too large.
    self.assertFalse(resource._IsImage(mock_blob))  # Bad image.

  def testTryGetImageSize(self):
    self.mox.StubOutWithMock(images, 'Image')
    mock_blob = self.mox.CreateMockAnything()
    mock_image = self.mox.CreateMockAnything()
    mock_transformed_image = self.mox.CreateMockAnything()
    mock_transformed_image.width = 123
    mock_transformed_image.height = 456
    dummy_data = object()

    mock_blob.key().AndReturn('a')
    images.Image(blob_key='a').AndReturn(mock_image)
    mock_image.crop(0.0, 0.0, 1.0, 1.0)
    mock_image.execute_transforms(output_encoding=images.JPEG).AndRaise(
        images.TransformationError)

    mock_blob.key().AndReturn('b')
    images.Image(blob_key='b').AndReturn(mock_image)
    mock_image.crop(0.0, 0.0, 1.0, 1.0)
    mock_image.execute_transforms(output_encoding=images.JPEG).AndReturn(
        dummy_data)
    images.Image(image_data=dummy_data).AndReturn(mock_transformed_image)

    self.mox.ReplayAll()
    self.assertEqual(resource._TryGetImageSize(mock_blob), None)
    self.assertEqual(resource._TryGetImageSize(mock_blob), (123, 456))

  def testIsResourceReferenced(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    resource1 = model.Resource(layer=layer, filename='a', type='icon')
    resource1.put()
    resource2 = model.Resource(layer=layer, filename='b', type='icon')
    resource2.put()
    resource3 = model.Resource(layer=layer, filename='c', type='icon')
    resource3.put()
    resource4 = model.Resource(layer=layer, filename='d', type='model')
    resource4.put()
    layer.icon = resource1
    layer.put()
    model.Folder(layer=layer, name='a', icon=resource2).put()
    model.Model(model=resource4, location=db.GeoPt(1, 2)).put()

    self.assertTrue(resource._IsResourceReferenced(resource1))
    self.assertTrue(resource._IsResourceReferenced(resource2))
    self.assertFalse(resource._IsResourceReferenced(resource3))
    self.assertTrue(resource._IsResourceReferenced(resource4))
