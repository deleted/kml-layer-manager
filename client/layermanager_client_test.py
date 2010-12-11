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
"""Tests for the client interface to the KML Layer Manager."""

import mox
import os
import StringIO
import unittest
import urllib2
import warnings
import zipfile

import layermanager_client as client


# Reuse whatever JSON library client.py found.
json = client.json

POST_TYPE = (('content_type', 'application/x-www-form-urlencoded'),)
# A dictionary of responses that the mock server replies with, keyed by a tuple
# of path, payload, and keyword arguments.
# pylint: disable-msg=C6005
MOCK_RESPONSES = {
    ('/path/to/get', None, ()): 'get1',
    ('/path/to/get', None, (('ab', 'cd'), ('ef', '\xe1\x88\xb4'))): 'get2',
    ('/path/to/get-fail', None, ()):
      urllib2.HTTPError('', 400, '', '', StringIO.StringIO('dummy')),
    ('/path/to/post', '', POST_TYPE): 'post1',
    ('/path/to/post', 'cd=%E1%88%B4&a=b', POST_TYPE): 'post2',
    ('/path/to/post', 'a=b&cd=%E1%88%B4', POST_TYPE): 'post2',
    ('/path/to/post-fail', '', POST_TYPE):
      urllib2.HTTPError('', 400, '', '', StringIO.StringIO('dummy')),
    ('/entity-update/42', 'a=bc&de=f', POST_TYPE): 'update',
    ('/entity-update/42', 'de=f&a=bc', POST_TYPE): 'update',
    ('/hello-update/13', 'x=y', POST_TYPE): 'update2',
    ('/schema-delete/99', 'abc=def', POST_TYPE): 'delete',
    ('/field-delete/472', '', POST_TYPE): '',
    ('/style-raw/7', None, (('id', 23), ('a', 'b'))): '["c", {"d": 3}]',
    ('/style-raw/7', None, (('a', 'b'), ('id', 23))): '["c", {"d": 3}]',
    ('/folder-list/3', None, (('u', 'w'),)): '[2, 4, 6, 8, 0]',
    ('/kml-list/123', None, ()): 'ab\nc\nd',
}


class MockHttpRpcServer(object):

  def __init__(self, **kwds):
    self.host = kwds['host']
    self.auth_function = kwds['auth_function']
    self.secure = kwds['secure']
    self.source = kwds['source']
    self.user_agent = kwds['user_agent']
    self.save_cookies = kwds['save_cookies']
    self._requests = []

  def Send(self, path, payload, **kwds):
    self._requests.append((path, payload, tuple(sorted(kwds.items()))))
    result = MOCK_RESPONSES[self._requests[-1]]
    if isinstance(result, Exception):
      raise result
    else:
      return result


def MakeHTTPError(code, location):
  http_error = urllib2.HTTPError(None, code, None, {'Location': location}, None)
  # urllib2 renames this for reasons of its own. Probably readability.
  http_error.headers = http_error.hdrs
  return http_error


class ClientTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.stubs.Set(client.appengine_rpc, 'HttpRpcServer', MockHttpRpcServer)
    self.client = client.LayersManagerClient('abc', 'def', 'ghi')
    self.stubs.Set(warnings, 'warn', lambda _: None)  # Ignore until needed.

  def testGetKMLResource(self):
    self.mox.StubOutWithMock(urllib2, 'urlopen')
    self.mox.StubOutWithMock(zipfile, 'ZipFile', use_mock_anything=True)
    mock_zipper = self.mox.CreateMockAnything()
    dummy_zipped_data = 'dummy_zipped_data'
    dummy_icon_data = 'dummy_icon_data'
    dummy_image_data = 'dummy_image_data'

    @mox.Func
    def VerifyZipData(in_file):
      self.assertEqual(in_file.read(), dummy_zipped_data)
      return True

    # Path into a KMZ. File exists.
    urllib2.urlopen('http://example.com/path/archive.kmz').AndReturn(
        StringIO.StringIO(dummy_zipped_data))
    zipfile.ZipFile(VerifyZipData).AndReturn(mock_zipper)
    mock_zipper.namelist().AndReturn(['resources/icon.png', 'icon.png'])
    mock_zipper.read('resources/icon.png').AndReturn(dummy_icon_data)

    # Path into a KMZ. File doesn't exist.
    urllib2.urlopen('http://example.com/path/archive.kmz').AndReturn(
        StringIO.StringIO(dummy_zipped_data))
    zipfile.ZipFile(VerifyZipData).AndReturn(mock_zipper)
    mock_zipper.namelist().AndReturn(['badpath/icon.png', 'icon.png'])

    # Path to a KMZ.
    urllib2.urlopen('http://example.com/path/archive.kmz?abc=def').AndReturn(
        StringIO.StringIO(dummy_zipped_data))

    # Path to a non-KMZ.
    urllib2.urlopen('http://example.com/path.ext/image.png?abc=def').AndReturn(
        StringIO.StringIO(dummy_image_data))

    self.mox.ReplayAll()

    url = 'http://example.com/path/archive.kmz/resources/icon.png?abc=def'
    self.assertEqual(client.GetKMLResource(url), dummy_icon_data)

    url = 'http://example.com/path/archive.kmz/resources/icon.png?abc=def'
    self.assertRaises(IOError, client.GetKMLResource, url)

    url = 'http://example.com/path/archive.kmz?abc=def'
    self.assertEqual(client.GetKMLResource(url), dummy_zipped_data)

    url = 'http://example.com/path.ext/image.png?abc=def'
    self.assertEqual(client.GetKMLResource(url), dummy_image_data)

  def testInit(self):
    self.assertEqual(self.client.rpc.host, 'abc')
    self.assertEqual(self.client.rpc.auth_function(), ('def', 'ghi'))
    self.assertEqual(self.client.rpc.secure, False)
    self.assertEqual(self.client.rpc.source, 'Layers CMS RPC')
    self.assertEqual(self.client.rpc.user_agent, None)
    self.assertEqual(self.client.rpc.save_cookies, False)

    secure_client = client.LayersManagerClient('a', 'b', 'c', secure=True)
    self.assertEqual(secure_client.rpc.secure, True)
    self.assertEqual(secure_client.rpc.save_cookies, False)

    cookie_client = client.LayersManagerClient('a', 'b', 'c', save_cookie=True)
    self.assertEqual(cookie_client.rpc.secure, False)
    self.assertEqual(cookie_client.rpc.save_cookies, True)

  def testGet(self):
    self.assertEqual(self.client.Get('/path/to/get'), 'get1')
    self.assertEqual(self.client.last_request, ('GET', '/path/to/get', {}))

    self.assertEqual(self.client.Get('/path/to/get', ab='cd', ef=u'\u1234'),
                     'get2')
    request = ('GET', '/path/to/get', {'ab': 'cd', 'ef': u'\u1234'})
    self.assertEqual(self.client.last_request, request)

    self.assertRaises(client.ManagerError, self.client.Get,
                      '/path/to/get-fail')
    self.assertEqual(self.client.last_request, ('GET', '/path/to/get-fail', {}))

  def testPost(self):
    self.assertEqual(self.client.Post('/path/to/post'), 'post1')
    self.assertEqual(self.client.last_request, ('POST', '/path/to/post', {}))

    self.assertEqual(
        self.client.Post('/path/to/post', a='b', cd=u'\u1234', e=None), 'post2')
    request = ('POST', '/path/to/post', {'a': 'b', 'cd': u'\u1234', 'e': None})
    self.assertEqual(self.client.last_request, request)

    self.assertRaises(client.ManagerError, self.client.Post,
                      '/path/to/post-fail')
    self.assertEqual(self.client.last_request,
                     ('POST', '/path/to/post-fail', {}))

  def testCreate(self):
    self.mox.StubOutWithMock(self.client, 'CreateResource')
    self.mox.StubOutWithMock(self.client, 'CreateLayer')
    self.mox.StubOutWithMock(self.client, 'CreateSchema')
    self.mox.StubOutWithMock(self.client, 'CreateEntity')
    self.mox.StubOutWithMock(self.client, 'Post')

    self.client.CreateResource(456, 'abc', 'def', 'ghi', None).AndReturn('rsrc')
    self.client.CreateLayer(a='b', cd='ef').AndReturn('lyr')
    self.client.CreateSchema(78, 'ij', 'gh', ()).AndReturn('scma')
    self.client.CreateEntity(90, kl='mn', op='rq').AndReturn('ntt')
    self.client.Post('/folder-create/159', st='uv', w='x').AndReturn('fld')

    self.mox.ReplayAll()

    self.assertEqual(self.client.Create(
        'resource', 456, type='abc', filename='def', url='ghi'), 'rsrc')
    self.assertEqual(self.client.Create('layer', 123, a='b', cd='ef'), 'lyr')
    self.assertEqual(self.client.Create(
        'schema', 78, fields='gh', name='ij'), 'scma')
    self.assertEqual(self.client.Create('entity', 90, kl='mn', op='rq'), 'ntt')
    self.assertEqual(self.client.Create('folder', 159, st='uv', w='x'), 'fld')

  def testUpdate(self):
    self.assertEqual(self.client.Update('entity', 42, a='bc', de='f'), 'update')
    self.assertEqual(self.client.Update('hello', 13, x='y'), 'update2')

  def testDelete(self):
    self.assertEqual(self.client.Delete('schema', 99, abc='def'), 'delete')
    self.assertEqual(self.client.Delete('field', 472), '')

  def testQuery(self):
    self.assertEqual(self.client.Query('style', 7, 23, a='b'), ['c', {'d': 3}])

  def testList(self):
    self.assertEqual(self.client.List('folder', 3, u='w'), [2, 4, 6, 8, 0])

  def testUndoLayers(self):
    self.client.layers_created = [123, 456, 789]
    self.mox.StubOutWithMock(self.client, 'Delete')

    self.client.Delete('layer', 123)
    self.client.Delete('layer', 456)
    self.client.Delete('layer', 789)

    self.mox.ReplayAll()

    self.client.UndoLayers()

  def testGetLayerKMLURL(self):
    self.assertEqual(self.client.GetLayerKMLURL(123),
                     'http://abc/serve/123/root.kml')

  def testGetAllLayerKMLURLs(self):
    self.assertEqual(self.client.GetAllLayerKMLURLs(123), ['ab', 'c', 'd'])

  def testGetResourceURL(self):
    self.assertEqual(self.client.GetResourceURL(135), 'http://abc/serve/0/r135')

  def GetRelativeResourceURL(self):
    self.assertEqual(self.client.GetRelativeResourceURL(42, 'hello.bye'),
                     'r42.bye')

  def testCreateSchema(self):
    self.mox.StubOutWithMock(self.client, 'Create')
    self.mox.StubOutWithMock(self.client, 'Post')

    # Schema, templates and fields.
    self.client.Post('/schema-create/911', name='xyz').AndReturn('741')
    self.client.Create('field', 911, schema_id=741,
                       name='ij', type='kl', tip='mn').AndReturn('73')
    self.client.Create('field', 911, schema_id=741,
                       name='op', type='qr', tip='').AndReturn('74')
    self.client.Create('template', 911, schema_id=741,
                       name='ab', text='cd').AndReturn('71')
    self.client.Create('template', 911, schema_id=741,
                       name='ef', text='gh').AndReturn('72')

    # Schema and a template.
    self.client.Post('/schema-create/911', name='xyz').AndReturn('641')
    self.client.Create('template', 911, schema_id=641,
                       name='ab', text='cd').AndReturn('61')

    # Schema only.
    self.client.Post('/schema-create/911', name='xyz').AndReturn('541')

    self.mox.ReplayAll()

    templates = [{'name': 'ab', 'text': 'cd'}, {'name': 'ef', 'text': 'gh'}]
    fields = [{'name': 'ij', 'type': 'kl', 'tip': 'mn'},
              {'name': 'op', 'type': 'qr'}]
    self.assertEqual(self.client.CreateSchema(911, 'xyz', fields, templates),
                     (741, [71, 72]))

    self.assertEqual(self.client.CreateSchema(911, 'xyz', [], templates[:1]),
                     (641, 61))

    self.assertEqual(self.client.CreateSchema(911, 'xyz', [], []), (541, None))

  def testCreateEntity(self):
    self.mox.StubOutWithMock(self.client, '_StandardizeEntity')
    self.mox.StubOutWithMock(self.client, 'Post')

    self.client._StandardizeEntity(123, {'abc': 'def', 'ghi': 456}).AndReturn(
        {'jkl': 'mno', 'prq': 789})
    self.client.Post('/entity-create/123', jkl='mno', prq=789)

    self.mox.ReplayAll()

    self.client.CreateEntity(123, abc='def', ghi=456)

  def testCreateLayer(self):
    self.mox.StubOutWithMock(self.client, 'Post')
    self.mox.StubOutWithMock(self.client, 'CreateResource')
    self.mox.StubOutWithMock(self.client, 'Update')
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(urllib2, 'urlopen')
    self.mox.StubOutWithMock(__builtins__, 'open')

    # No icon.
    self.client.Post('/layer-create/0', x='y').AndReturn('abc')

    # Local icon.
    os.path.exists('def').AndReturn(True)
    open('def').AndReturn(StringIO.StringIO('xyz'))
    self.client.Post('/layer-create/0', x='z').AndReturn('ghi')
    self.client.CreateResource('ghi', 'icon', 'def', data='xyz').AndReturn('j')
    self.client.Update('layer', 'ghi', icon='j')

    # Remote icon.
    os.path.exists('klm').AndReturn(False)
    urllib2.urlopen('klm').AndReturn(StringIO.StringIO('uvw'))
    self.client.Post('/layer-create/0', x='z').AndReturn('nop')
    self.client.CreateResource('nop', 'icon', 'klm', data='uvw').AndReturn('q')
    self.client.Update('layer', 'nop', icon='q')

    self.mox.ReplayAll()

    self.assertEqual(self.client.CreateLayer(x='y'), 'abc')
    self.assertEqual(self.client.CreateLayer(x='z', icon='def'), 'ghi')
    self.assertEqual(self.client.CreateLayer(x='z', icon='klm'), 'nop')

  def testCreateResourceWithURL(self):
    self.mox.StubOutWithMock(self.client.rpc, 'Send')
    self.mox.StubOutWithMock(self.client, '_GetUploadURL')
    self.mox.StubOutWithMock(self.client, '_FollowResourceRedirect')

    self.client.rpc.Send(
        '/resource-create/195', 'url=there&type=typ&filename=myname',
        content_type='application/x-www-form-urlencoded').AndRaise(
        MakeHTTPError(12345, 'xyz'))
    self.client._FollowResourceRedirect(195, 12345, 'xyz').AndReturn('4817')

    self.mox.ReplayAll()

    resource_id = self.client.CreateResource(195, 'typ', 'myname', url='there')
    self.assertEqual(resource_id, '4817')

  def testCreateResourceWithFile(self):
    self.mox.StubOutWithMock(self.client.rpc, 'Send')
    self.mox.StubOutWithMock(self.client, '_GetUploadURL')
    self.mox.StubOutWithMock(self.client, '_MultiPartEncode')
    self.mox.StubOutWithMock(self.client, '_FollowResourceRedirect')

    self.client._GetUploadURL(256).AndReturn(['/hello/path', None])
    self.client._MultiPartEncode(
        {'type': 'typ', 'filename': 'myname'},
        {'file': ('myname', '01010')}).AndReturn(('test/ctype', 'enc-args'))
    self.client.rpc.Send(
        '/hello/path', 'enc-args', content_type='test/ctype').AndRaise(
        MakeHTTPError(891, 'xyz'))
    self.client._FollowResourceRedirect(256, 891, 'xyz').AndReturn('235789')

    self.mox.ReplayAll()

    resource_id = self.client.CreateResource(256, 'typ', 'myname', data='01010')
    self.assertEqual(resource_id, '235789')

  def testBatchCreateResources(self):
    self.mox.StubOutWithMock(self.client, '_GetUploadURL')
    self.mox.StubOutWithMock(self.client.rpc, 'Send')
    self.mox.StubOutWithMock(self.client, '_MultiPartEncode')
    self.mox.StubOutWithMock(self.client, '_FollowResourceRedirect')

    resources = [{'filename': 'abc', 'type': 'asm', 'url': 'dfl'},
                 {'filename': 'def', 'type': 'mka', 'file': 'dsa'}]
    fields = {'filename0': 'abc', 'type0': 'asm', 'url0': 'dfl',
              'filename1': 'def', 'type1': 'mka'}
    files = {'file1': ('def', 'dsa')}

    self.client._GetUploadURL(641).AndReturn([None, '/hello/path'])
    self.client._MultiPartEncode(fields, files).AndReturn(('ijk', 'fgh'))
    self.client.rpc.Send(
        '/hello/path', 'fgh', content_type='ijk').AndRaise(
        MakeHTTPError(234, 'dhs'))
    self.client._FollowResourceRedirect(641, 234, 'dhs').AndReturn('15,16\n')

    self.mox.ReplayAll()
    self.assertEqual(self.client.BatchCreateResources(641, resources), [15, 16])

  def testBatchCreateEntitiesSucceeding(self):
    self.mox.StubOutWithMock(self.client, 'Post')

    entities = [{'name': 'abc'}, {'name': 'def'}]
    encoded = json.dumps(entities)

    self.client.Post('/entity-bulk/2342', entities=encoded).AndReturn('4,8\n')
    self.mox.ReplayAll()
    self.assertEqual(self.client.BatchCreateEntities(2342, entities), [4, 8])

  def testBatchCreateEntitiesReturningError(self):
    self.mox.StubOutWithMock(self.client, 'Post')
    self.client.Post('/entity-bulk/188', entities='[]').AndReturn('4\nabc')
    self.mox.ReplayAll()
    self.assertRaises(
        client.ManagerError, self.client.BatchCreateEntities, 188, [], 0)

  def testBatchCreateEntitiesTimeout(self):
    self.mox.StubOutWithMock(self.client, 'Post')

    entities = [{'name': 'abc'}, {'name': 'def'}, {'name': 'ghi'}]
    encoded1 = json.dumps(entities)
    encoded2 = json.dumps(entities[2:])
    result1 = '4,5\nRan our of time.'
    result2 = '6\n'

    self.client.Post('/entity-bulk/123', entities=encoded1).AndReturn(result1)
    self.client.Post('/entity-bulk/123', entities=encoded2).AndReturn(result2)

    self.mox.ReplayAll()

    self.assertEqual(self.client.BatchCreateEntities(123, entities), [4, 5, 6])

  def testBatchCreateEntitiesRetryOnError(self):
    self.mox.StubOutWithMock(self.client, 'Post')
    entities = [{'a': 'b'}, {'c': 'd'}, {'e': 'f'}]
    encoded1 = json.dumps(entities)
    encoded2 = json.dumps(entities[1:])
    self.client.Post('/entity-bulk/42', entities=encoded1).AndReturn('3\nabc')
    self.client.Post('/entity-bulk/42', entities=encoded2).AndReturn('4,5\n')
    self.mox.ReplayAll()
    self.assertEqual(self.client.BatchCreateEntities(42, entities, 2),
                     [3, 4, 5])

  def testFetchAndUpload(self):
    self.mox.StubOutWithMock(client, 'GetKMLResource')
    self.mox.StubOutWithMock(self.client, 'CreateResource')

    client.GetKMLResource('http://xyz.uvw/ab/cd.ef').AndReturn('dummy-data')
    self.client.CreateResource(
        123, 'icon', 'cd.ef', data='dummy-data').AndReturn('dummy-result')

    self.mox.ReplayAll()

    self.assertEqual(
        self.client.FetchAndUpload(123, 'http://xyz.uvw/ab/cd.ef', 'icon'),
        'dummy-result')

  def testFindAndCreateIcons(self):
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(self.client, 'FetchAndUpload')
    self.mox.StubOutWithMock(self.client, 'CreateResource')
    dummy_layer = object()
    url = 'http://hello.world.xyz/some/path.png'

    os.path.exists('uvw').AndReturn(True)
    self.client.FetchAndUpload(dummy_layer, 'uvw', 'icon').AndReturn(123)
    os.path.exists(url).AndReturn(False)
    self.client.CreateResource(
        dummy_layer, 'icon', 'path.png', url=url).AndReturn(456)
    os.path.exists('def').AndReturn(False)

    self.mox.ReplayAll()

    # Existing local path.
    folder_args = {'x': 'yz', 'icon': 'uvw'}
    self.client._FindAndCreateIcons('folder', dummy_layer, folder_args)
    self.assertEqual(folder_args, {'x': 'yz', 'icon': 123})

    # URL.
    style_args = {'x': 'yz', 'highlight_icon': url}
    self.client._FindAndCreateIcons('style', dummy_layer, style_args)
    self.assertEqual(style_args, {'x': 'yz', 'highlight_icon': 456})

    # ID.
    link_args = {'x': 'yz', 'icon': '789'}
    self.client._FindAndCreateIcons('link', dummy_layer, link_args)
    self.assertEqual(link_args, {'x': 'yz', 'icon': '789'})

    # Non-existing local path.
    link_args = {'x': 'yz', 'icon': 'def'}
    self.assertRaises(client.ManagerError, self.client._FindAndCreateIcons,
                      'link', dummy_layer, link_args)

  def testFollowResourceRedirect(self):
    self.mox.StubOutWithMock(self.client, 'Get')

    self.client.Get('/c', d='/').AndReturn('400\nx\ny\nz\nw')
    self.client.Get('/c', d='/').AndReturn('200\nx\ny\nz\nw')

    self.mox.ReplayAll()

    # Non-redirect error status code.
    self.assertRaises(
        client.ManagerError, self.client._FollowResourceRedirect,
        123, 404, 'abc')
    # Non-redirect valid status code.
    self.assertRaises(
        client.ManagerError, self.client._FollowResourceRedirect,
        123, 200, 'abc')
    # Get() no succeeding.
    self.assertRaises(
        client.ManagerError, self.client._FollowResourceRedirect,
        123, 302, 'http://a.b/c?d=%2F')
    # Success.
    result = self.client._FollowResourceRedirect(123, 302, 'http://a.b/c?d=%2F')
    self.assertEqual(result, 'x')

  def testGetUploadURL(self):
    self.mox.StubOutWithMock(self.client, 'Get')

    self.client.Get('/resource-raw/456', error='dummy').AndReturn(
        'a\nb\nc\nhttp://a1.b2.cc/hello#x\nhttp://d3.e4.ff/goodbye?q=w')

    self.client.Get('/resource-raw/789', error='dummy').AndReturn(
        'a\nb\nc\nhttp://a1.b2.cc/this\nhttp://d3.e4.ff/that')

    self.mox.ReplayAll()

    # Saved URL exists for this layer.
    self.client._upload_url = (123, 'http://ab.cd/ef?gh=ij#kl', 'http://m.no/')
    self.assertEqual(self.client._GetUploadURL(123), ('/ef?gh=ij', '/'))

    # Saved URL exists for another layer.
    self.client._upload_url = (123, 'http://ab.cd/ef?gh=ij#kl', 'http://m.no/')
    self.assertEqual(self.client._GetUploadURL(456), ('/hello', '/goodbye?q=w'))

    # No saved URL exists.
    self.client._upload_url = None
    self.assertEqual(self.client._GetUploadURL(789), ('/this', '/that'))

  def testStandardizeEntityFormatChange(self):
    geometryless = {'a': 'b', 'c': 'd'}

    single_standard = {
        'geometries': json.dumps([{'fields': {'x': 'y'}, 'type': 'Point'}]),
        'e': 'f'
    }
    single_encoded = {
        'geometry': json.dumps({'fields': {'x': 'y'}, 'type': 'Point'}),
        'e': 'f'
    }
    single_decoded = {
        'geometry': {'type': 'Point', 'fields': {'x': 'y'}},
        'e': 'f'
    }
    single_basic = {
        'geometry': ('Point', {'x': 'y'}),
        'e': 'f'
    }

    multi_standard = {
        'geometries': json.dumps([
            {'fields': {'x': 'y'}, 'type': 'Point'},
            {'fields': {'z': 'u'}, 'type': 'LineString'}
        ]),
        'e': 'f'
    }
    multi_decoded = {
        'geometries': [
            {'fields': {'x': 'y'}, 'type': 'Point'},
            {'fields': {'z': 'u'}, 'type': 'LineString'}
        ],
        'e': 'f'
    }
    multi_basic = {
        'geometries': [('Point', {'x': 'y'}), ('LineString', {'z': 'u'})],
        'e': 'f'
    }

    self.assertEqual(self.client._StandardizeEntity(object(), geometryless),
                     geometryless)

    self.assertEqual(self.client._StandardizeEntity(object(), single_standard),
                     single_standard)
    self.assertEqual(self.client._StandardizeEntity(object(), single_encoded),
                     single_standard)
    self.assertEqual(self.client._StandardizeEntity(object(), single_decoded),
                     single_standard)
    self.assertEqual(self.client._StandardizeEntity(object(), single_basic),
                     single_standard)

    self.assertEqual(self.client._StandardizeEntity(object(), multi_standard),
                     multi_standard)
    self.assertEqual(self.client._StandardizeEntity(object(), multi_decoded),
                     multi_standard)
    self.assertEqual(self.client._StandardizeEntity(object(), multi_basic),
                     multi_standard)

  def testStandardizeEntityResourceFetch(self):
    self.mox.StubOutWithMock(os.path, 'exists')
    self.mox.StubOutWithMock(self.client, 'FetchAndUpload')
    self.mox.StubOutWithMock(self.client, 'CreateResource')
    dummy_layer = object()
    url = 'http://hello.world.xyz/some/path.png'

    os.path.exists('abc').AndReturn(True)
    self.client.FetchAndUpload(dummy_layer, 'abc', 'model').AndReturn(123)
    os.path.exists(url).AndReturn(False)
    self.client.CreateResource(
        dummy_layer, 'image', 'path.png', url=url).AndReturn(456)

    self.mox.ReplayAll()

    entity = {
        'geometries': [
            ('Model', {'model': 'abc'}),
            ('GroundOverlay', {'image': url}),
            ('GroundOverlay', {'image': '789'}),
            ('GroundOverlay', {'image': 42})
        ],
    }
    standardized_entity = {
        'geometries': json.dumps([
            {'type': 'Model', 'fields': {'model': 123}},
            {'type': 'GroundOverlay', 'fields': {'image': 456}},
            {'type': 'GroundOverlay', 'fields': {'image': '789'}},
            {'type': 'GroundOverlay', 'fields': {'image': 42}}
        ]),
    }
    self.assertEqual(self.client._StandardizeEntity(dummy_layer, entity),
                     standardized_entity)

  def testEncodeDict(self):
    original = {
        u'\u1234': 'a',
        'bc': u'd\u5678',
        'ef': 'gh',
        u'x\u1928y': u'z\u2537w'
    }
    expected = {
        '\xe1\x88\xb4': 'a',
        'bc': 'd\xe5\x99\xb8',
        'ef': 'gh',
        'x\xe1\xa4\xa8y': 'z\xe2\x94\xb7w'
    }
    self.assertEqual(self.client._EncodeDict(original), expected)

  def testVerifyArgs(self):
    received_warnings = []
    self.stubs.Set(warnings, 'warn', received_warnings.append)
    self.assertEqual(self.client.Update('entity', 42, a='bc', de='f'), 'update')
    self.assertEqual(self.client.Update('hello', 13, x='y'), 'update2')
    self.assertEqual(received_warnings, [
        'Unknown argument for entity: a',
        'Unknown argument for entity: de',
        'Unknown object type: hello'
    ])

  def testMultiPartEncode(self):
    self.mox.StubOutWithMock(os, 'urandom')

    os.urandom(16).AndReturn('\n5\xf4%\xd2*lshiabv12$')

    self.mox.ReplayAll()

    fields = {'abc': 'def', 'ghi': 'jkl'}
    files = {'mno': ('pqr', 'stu'), 'vwx': ('y\xEEz', '1w2e')}
    encoded = self.client._MultiPartEncode(fields, files)
    expected_type = 'multipart/form-data; boundary=CjX0JdIqbHNoaWFidjEyJA=='
    expected_data = """
--CjX0JdIqbHNoaWFidjEyJA==
Content-Disposition: form-data; name="abc"

def
--CjX0JdIqbHNoaWFidjEyJA==
Content-Disposition: form-data; name="ghi"

jkl
--CjX0JdIqbHNoaWFidjEyJA==
Content-Disposition: form-data; name="vwx"; filename="y\xEEz"
Content-Type: application/octet-stream

1w2e
--CjX0JdIqbHNoaWFidjEyJA==
Content-Disposition: form-data; name="mno"; filename="pqr"
Content-Type: application/octet-stream

stu
--CjX0JdIqbHNoaWFidjEyJA==--
""".strip().replace('\n', '\r\n')
    self.assertEqual(encoded, (expected_type, expected_data))


if __name__ == '__main__':
  unittest.main()
