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

"""Small tests for utility functions."""


import os
from google.appengine.ext import db
from lib.mox import mox
import util


class UtilTest(mox.MoxTestBase):

  def testGetURL(self):
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'a', 'SERVER_PORT': '123'})
    self.assertEqual(util.GetURL(''), 'http://a:123/')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'b', 'SERVER_PORT': ''})
    self.assertEqual(util.GetURL(''), 'http://b/')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'c'})
    self.assertEqual(util.GetURL(''), 'http://c/')

    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'a'})
    self.assertEqual(util.GetURL('/'), 'http://a/')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'a', 'SERVER_PORT': '123'})
    self.assertEqual(util.GetURL('/xyz'), 'http://a:123/xyz')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'a'})
    self.assertEqual(util.GetURL('.fake.com/xyz'), 'http://a/.fake.com/xyz')

  def testGetInstanceRequiredWithoutLayer(self):
    mock_model = self.mox.CreateMockAnything()
    mock_model.__name__ = 'dummy'
    mock_model.get_by_id(123).AndReturn('dummy-123')
    mock_model.get_by_id(456).AndReturn('dummy-456')
    mock_model.get_by_id(0).AndRaise(db.BadKeyError)
    mock_model.get_by_id(-1).AndReturn(None)
    mock_model.get_by_id(5).AndReturn(None)
    self.mox.ReplayAll()
    self.assertEqual(util.GetInstance(mock_model, 123), 'dummy-123')
    self.assertEqual(util.GetInstance(mock_model, '456'), 'dummy-456')
    self.assertRaises(util.BadRequest, util.GetInstance, mock_model, 0)
    self.assertRaises(util.BadRequest, util.GetInstance, mock_model, -1)
    self.assertRaises(util.BadRequest, util.GetInstance, mock_model, 5)
    self.assertRaises(util.BadRequest, util.GetInstance, mock_model, 'asd')

  def testGetInstanceOptionalWithoutLayer(self):
    mock_model = self.mox.CreateMockAnything()
    mock_model.__name__ = 'dummy'
    mock_model.get_by_id(9).AndReturn('dummy-9')
    mock_model.get_by_id(10).AndReturn('dummy-10')
    mock_model.get_by_id(-1).AndReturn(None)
    mock_model.get_by_id(5).AndReturn(None)
    self.mox.ReplayAll()
    self.assertEqual(util.GetInstance(mock_model, 9, required=False), 'dummy-9')
    self.assertEqual(util.GetInstance(mock_model, '10', required=False),
                     'dummy-10')
    self.assertEqual(util.GetInstance(mock_model, 0, required=False), None)
    self.assertRaises(util.BadRequest, util.GetInstance,
                      mock_model, -1, required=False)
    self.assertRaises(util.BadRequest, util.GetInstance,
                      mock_model, 5, required=False)
    self.assertRaises(util.BadRequest, util.GetInstance,
                      mock_model, 'asd', required=False)

  def testGetInstanceRequiredWithLayer(self):
    mock_model = self.mox.CreateMockAnything()
    mock_model.__name__ = 'dummy'
    mock_layer = self.mox.CreateMockAnything()
    mock_instance = self.mox.CreateMockAnything()
    mock_instance.layer = self.mox.CreateMockAnything()

    mock_model.get_by_id(1).AndReturn(mock_instance)
    mock_instance.layer.key().AndReturn(mock_instance.layer)
    mock_instance.layer.id().AndReturn(2)
    mock_layer.key().AndReturn(mock_layer)
    mock_layer.id().AndReturn(2)

    mock_model.get_by_id(3).AndReturn(mock_instance)
    mock_instance.layer.key().AndReturn(mock_instance.layer)
    mock_instance.layer.id().AndReturn(4)
    mock_layer.key().AndReturn(mock_layer)
    mock_layer.id().AndReturn(5)

    mock_model.get_by_id(6).AndReturn(None)

    mock_model.get_by_id(0).AndRaise(db.BadKeyError)

    self.mox.ReplayAll()
    self.assertEqual(util.GetInstance(mock_model, 1, mock_layer), mock_instance)
    self.assertRaises(util.BadRequest, util.GetInstance,
                      mock_model, 3, mock_layer)
    self.assertRaises(util.BadRequest, util.GetInstance,
                      mock_model, 6, mock_layer)
    self.assertRaises(util.BadRequest, util.GetInstance,
                      mock_model, 0, mock_layer)

  def testGetInstanceOptionalWithLayer(self):
    mock_model = self.mox.CreateMockAnything()
    mock_model.__name__ = 'dummy'
    mock_model.get_by_id(6).AndReturn(None)
    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, util.GetInstance,
                      mock_model, 6, 'layer-dummy', False)
    self.assertEqual(util.GetInstance(mock_model, 0, 'layer', False), None)

  def testGetRequestSourceType(self):
    self.mox.StubOutWithMock(util, 'GetURL')
    mock_request = self.mox.CreateMockAnything()
    mock_request.headers = self.mox.CreateMockAnything()

    mock_request.headers.get('X-Requested-With').AndReturn('XMLHttpRequest')

    mock_request.headers.get('X-Requested-With').AndReturn('dummy')
    mock_request.headers.get('X-AppCfg-API-Version').AndReturn('1')

    mock_request.headers.get('X-Requested-With').AndReturn('dummy')
    mock_request.headers.get('X-AppCfg-API-Version').AndReturn(None)
    mock_request.headers.get('X-AppEngine-QueueName').AndReturn('dummy')

    # Origin supplied.
    mock_request.headers.get('X-Requested-With').AndReturn('dummy')
    mock_request.headers.get('X-AppCfg-API-Version').AndReturn(None)
    mock_request.headers.get('X-AppEngine-QueueName').AndReturn(None)
    util.GetURL('').AndReturn('http://x.y:1/')
    mock_request.headers.get('Origin', '').AndReturn('http://x.y:1')

    # No Origin; use Referer.
    mock_request.headers.get('X-Requested-With').AndReturn('dummy')
    mock_request.headers.get('X-AppCfg-API-Version').AndReturn(None)
    mock_request.headers.get('X-AppEngine-QueueName').AndReturn(None)
    util.GetURL('').AndReturn('http://x.y:1/')
    mock_request.headers.get('Origin', '').AndReturn('')
    mock_request.headers.get('Referer', '').AndReturn('http://x.y:1/z')

    # Invalid Origin.
    mock_request.headers.get('X-Requested-With').AndReturn('dummy')
    mock_request.headers.get('X-AppCfg-API-Version').AndReturn(None)
    mock_request.headers.get('X-AppEngine-QueueName').AndReturn(None)
    util.GetURL('').AndReturn('http://other/')
    mock_request.headers.get('Origin', '').AndReturn('http://x.y:1')

    # No origin or referer; edge values for headers
    mock_request.headers.get('X-Requested-With').AndReturn('dummy')
    mock_request.headers.get('X-AppCfg-API-Version').AndReturn('0')
    mock_request.headers.get('X-AppEngine-QueueName').AndReturn('')
    util.GetURL('').AndReturn('http://other/')
    mock_request.headers.get('Origin', '').AndReturn('')
    mock_request.headers.get('Referer', '').AndReturn('')

    self.mox.ReplayAll()
    self.assertEqual(util.GetRequestSourceType(mock_request), 'xhr')
    self.assertEqual(util.GetRequestSourceType(mock_request), 'api')
    self.assertEqual(util.GetRequestSourceType(mock_request), 'queue')
    self.assertEqual(util.GetRequestSourceType(mock_request), 'normal')
    self.assertEqual(util.GetRequestSourceType(mock_request), 'normal')
    self.assertEqual(util.GetRequestSourceType(mock_request), 'unknown')
    self.assertEqual(util.GetRequestSourceType(mock_request), 'unknown')
