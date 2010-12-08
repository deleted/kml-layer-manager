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

"""Small tests for the custom Django template tag and filter functions."""


import os
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from lib.mox import mox
import model
import settings
from template_functions import entities
from template_functions import kml
from template_functions import pages
import util


class MockEntity(object):
  def __init__(self, entity_id, layer_id=None, folder_id=None):
    self._id = entity_id
    if layer_id:
      self.layer = MockEntity(layer_id)
    else:
      self.layer = None
    if folder_id:
      self.folder = MockEntity(folder_id)
    else:
      self.folder = None

  def key(self):  # pylint: disable-msg=C6409
    return self

  def id(self):  # pylint: disable-msg=C6409
    return self._id


class EntitiesTemplateFunctionsTest(mox.MoxTestBase):

  def testRenderContextSuppliedTag(self):
    dummy_function = self.mox.CreateMockAnything()
    tag = entities._ContextSuppliedTag(dummy_function, ['a', '"b"', 'c'])
    self.mox.StubOutWithMock(pages.template.django.template, 'resolve_variable')

    pages.template.django.template.resolve_variable(
        'a', 'dummy-context').AndReturn('ra')
    pages.template.django.template.resolve_variable(
        'c', 'dummy-context').AndReturn('rc')
    dummy_function('dummy-context', 'ra', 'b', 'rc').AndReturn('executed')
    self.mox.ReplayAll()
    self.assertEqual(tag.render('dummy-context'), 'executed')

  def testParseContextSuppliedTag(self):

    def DummyFunction(_, __, ___):
      raise RuntimeError('Should not be called!')

    class DummyTokenizer(object):

      def __init__(self, contents):
        self.contents = contents

      def split_contents(self):  # pylint: disable-msg=C6409
        return self.contents.split(' ')

    # Success.
    tag = entities._ContextSuppliedTag.Parse(
        DummyTokenizer('a b c'), DummyFunction)
    self.assertEqual(tag.function, DummyFunction)
    self.assertEqual(tag.arguments, ['b', 'c'])

    # Failure - not enough parameters.
    self.assertRaises(template.django.template.TemplateSyntaxError,
                      entities._ContextSuppliedTag.Parse,
                      DummyTokenizer('a'), DummyFunction)

    # Failure - too many parameters.
    self.assertRaises(template.django.template.TemplateSyntaxError,
                      entities._ContextSuppliedTag.Parse,
                      DummyTokenizer('a b c d e'), DummyFunction)

  def testRegisterContextSuppliedTag(self):
    dummy_token = object()
    dummy_function = self.mox.CreateMockAnything()
    dummy_function.__name__ = 'DummyFunction'

    self.mox.StubOutWithMock(entities, 'register')
    self.mox.StubOutWithMock(entities._ContextSuppliedTag, 'Parse')

    @mox.Func
    def VerifyParser(parser):
      parser(object(), dummy_token)
      return True

    entities.register.tag('DummyFunction', VerifyParser)
    entities._ContextSuppliedTag.Parse(dummy_token, dummy_function)

    self.mox.ReplayAll()
    self.assertEqual(entities._ContextSuppliedTag.Register(dummy_function),
                     dummy_function)

  def testGetEntitySiblings(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    other_layer = model.Layer(name='b', world='earth')
    other_layer.put()
    folder = model.Folder(layer=layer, name='c')
    folder_id = folder.put().id()
    schema = model.Schema(layer=layer, name='z')
    schema.put()
    template = model.Template(layer=layer, schema=schema, name='y', text='x')
    template_id = template.put().id()
    entity1 = model.Entity(layer=layer, name='c', template=template)
    entity1_id = entity1.put().id()
    entity2_id = model.Entity(layer=layer, name='e',
                              template=template).put().id()
    entity3_id = model.Entity(layer=other_layer, name='f',
                              template=template).put().id()
    entity4_id = model.Entity(layer=layer, name='g', template=template,
                              folder=folder, folder_index=2).put().id()
    entity5 = model.Entity(layer=layer, name='g', folder=folder, folder_index=1,
                           template=template)
    entity5_id = entity5.put().id()
    cache = {'entity_siblings': {}}

    self.assertEqual(entities._GetEntitySiblings(entity1, cache),
                     [entity1_id, entity2_id])
    self.assertEqual(cache, {'entity_siblings': {
        layer_id: [entity1_id, entity2_id]}
    })

    self.assertEqual(entities._GetEntitySiblings(entity5, cache),
                     [entity5_id, entity4_id])
    self.assertEqual(cache, {'entity_siblings': {
        layer_id: [entity1_id, entity2_id],
        folder_id: [entity5_id, entity4_id]
    }})

  def testGetFlyToLinkWithGoodData(self):
    self.assertEqual(entities._GetFlyToLink(42, 'abc'), '#id42;abc')
    self.assertEqual(entities._GetFlyToLink(42, 'abc', 'def'), 'def')
    link_template = 'a' + settings.BALLOON_LINK_PLACEHOLDER + 'b'
    self.assertEqual(entities._GetFlyToLink(42, 'abc', link_template), 'aid42b')

  def testGetFlyToLinkWithBadData(self):
    self.assertRaises(TypeError, entities._GetFlyToLink, 'hello', 'balloon')
    self.assertRaises(AttributeError, entities._GetFlyToLink, 1, 'balloon', 2)

  def testGetOffsetLink(self):
    mock_entity = MockEntity(6, 16)
    mock_entity.layer.auto_managed = False
    self.mox.StubOutWithMock(pages.template.django.template, 'resolve_variable')
    self.mox.StubOutWithMock(entities, '_GetEntitySiblings')
    self.mox.StubOutWithMock(entities, '_GetFlyToLink')
    dummy_siblings_list = [5, 6, 7, 8, 9, 10]

    pages.template.django.template.resolve_variable(
        '_cache', 'dummy-context').AndReturn('dummy-cache')
    pages.template.django.template.resolve_variable(
        '_link_template', 'dummy-context').AndReturn('dummy-template')
    entities._GetEntitySiblings(mock_entity, 'dummy-cache').AndReturn(
        dummy_siblings_list)
    entities._GetFlyToLink(8, 'balloon', 'dummy-template').AndReturn(
        'dummy-link1')

    pages.template.django.template.resolve_variable(
        '_cache', 'dummy-context').AndReturn('dummy-cache')
    pages.template.django.template.resolve_variable(
        '_link_template', 'dummy-context').AndReturn('dummy-template')
    entities._GetEntitySiblings(mock_entity, 'dummy-cache').AndReturn(
        dummy_siblings_list)
    entities._GetFlyToLink(10, 'balloon', 'dummy-template').AndReturn(
        'dummy-link2')

    self.mox.ReplayAll()

    link = entities._GetOffsetLink('dummy-context', mock_entity, 2, 'balloon')
    self.assertEqual(link, 'dummy-link1')

    link = entities._GetOffsetLink('dummy-context', mock_entity, -2, 'balloon')
    self.assertEqual(link, 'dummy-link2')

    mock_entity.layer.auto_managed = True
    self.assertRaises(ValueError, entities._GetOffsetLink,
                      'dummy-context', mock_entity, -2, 'balloon')

  def testPrevLink(self):
    self.mox.StubOutWithMock(entities, '_GetOffsetLink')
    entities._GetOffsetLink('a', 'b', -1, 'balloonFlyto').AndReturn('c')
    self.mox.ReplayAll()
    self.assertEqual(entities.PrevLink('a', 'b'), 'c')

  def testNextLink(self):
    self.mox.StubOutWithMock(entities, '_GetOffsetLink')
    entities._GetOffsetLink('a', 'b', 1, 'balloonFlyto').AndReturn('c')
    self.mox.ReplayAll()
    self.assertEqual(entities.NextLink('a', 'b'), 'c')

  def testPrettifyCoordinates180(self):
    point = db.GeoPt(1, 2)
    self.assertEqual(entities.PrettifyCoordinates180(point),
                     '1.00&deg;N 2.00&deg;E')
    point = db.GeoPt(1.2, 3.4567)
    self.assertEqual(entities.PrettifyCoordinates180(point),
                     '1.20&deg;N 3.46&deg;E')
    point = db.GeoPt(45, -2)
    self.assertEqual(entities.PrettifyCoordinates180(point),
                     '45.00&deg;N 2.00&deg;W')
    point = db.GeoPt(-90, -2.56)
    self.assertEqual(entities.PrettifyCoordinates180(point),
                     '90.00&deg;S 2.56&deg;W')

  def testPrettifyCoordinates360(self):
    point = db.GeoPt(1, 2)
    self.assertEqual(entities.PrettifyCoordinates360(point),
                     '1.00&deg;N 2.00&deg;E')
    point = db.GeoPt(1.2, 3.4567)
    self.assertEqual(entities.PrettifyCoordinates360(point),
                     '1.20&deg;N 3.46&deg;E')
    point = db.GeoPt(45, -2)
    self.assertEqual(entities.PrettifyCoordinates360(point),
                     '45.00&deg;N 358.00&deg;E')
    point = db.GeoPt(-90, -2.56)
    self.assertEqual(entities.PrettifyCoordinates360(point),
                     '90.00&deg;S 357.44&deg;E')

  def testKilometerToMile(self):
    self.assertEqual(entities.KilometerToMile(0), 0)
    self.assertEqual(entities.KilometerToMile(1), 0.621371192)
    self.assertEqual(entities.KilometerToMile(1.0), 0.621371192)
    self.assertRaises(TypeError, entities.KilometerToMile, '0')
    self.assertRaises(TypeError, entities.KilometerToMile, '1.0')
    self.assertRaises(TypeError, entities.KilometerToMile, None)


class KMLTemplateFunctionsTest(mox.MoxTestBase):

  def testFormatCoordinatesWithoutAltitudes(self):
    self.assertEqual(kml.FormatCoordinates([]), '')
    self.assertEqual(kml.FormatCoordinates([db.GeoPt(1, 2)]), '2.0,1.0')
    points = [db.GeoPt(1, 2), db.GeoPt(3.456, 7.0)]
    self.assertEqual(kml.FormatCoordinates(points), '2.0,1.0 7.0,3.456')

  def testFormatCoordinatesWithValidAltitudes(self):
    self.assertEqual(kml.FormatCoordinates([], []), '')
    self.assertEqual(kml.FormatCoordinates([db.GeoPt(1, 2)], [3]),
                     '2.0,1.0,3')
    self.assertEqual(kml.FormatCoordinates([db.GeoPt(1, 2)], [3.0]),
                     '2.0,1.0,3.0')
    self.assertEqual(kml.FormatCoordinates([db.GeoPt(1, 2)], []),
                     '2.0,1.0')
    points = [db.GeoPt(1, 2), db.GeoPt(3.456, 7.0)]
    self.assertEqual(kml.FormatCoordinates(points, [8, 9.01]),
                     '2.0,1.0,8 7.0,3.456,9.01')

  def testFormatCoordinatesWithInvalidAltitudesCount(self):
    self.assertRaises(ValueError, kml.FormatCoordinates, [], [1])
    self.assertRaises(ValueError, kml.FormatCoordinates,
                      [db.GeoPt(1, 2)], [4, 5, 6])

  def testFormatCoordinatesWithInvalidTypes(self):
    self.assertRaises(AttributeError, kml.FormatCoordinates, [2])
    self.assertRaises(TypeError, kml.FormatCoordinates, db.GeoPt(1, 2))
    # Expected artifacts of duck typing.
    self.assertEqual(kml.FormatCoordinates([db.GeoPt(1, 2)], [None]),
                     '2.0,1.0,None')
    self.assertEqual(kml.FormatCoordinates([db.GeoPt(1, 2)], 'a'),
                     '2.0,1.0,a')
    self.assertRaises(ValueError, kml.FormatCoordinates, [db.GeoPt(1, 2)], 'ab')

  def testIsNotNone(self):
    self.assertEqual(kml.IsNotNone('a'), True)
    self.assertEqual(kml.IsNotNone(''), True)
    self.assertEqual(kml.IsNotNone('None'), True)
    self.assertEqual(kml.IsNotNone(None), False)

  def testEscapeForXMLWithSafeShortASCIIStrings(self):
    self.assertEqual(kml.EscapeForXML('a'), 'a')
    self.assertEqual(kml.EscapeForXML('hello'), 'hello')
    self.assertEqual(kml.EscapeForXML('x' * 100), 'x' * 100)
    self.assertNotEqual(kml.EscapeForXML('x' * 101), 'x' * 101)

  def testEscapeForXMLWithUnsafeShortASCIIStrings(self):
    self.assertEqual(kml.EscapeForXML('a&b'), 'a&amp;b')
    self.assertEqual(kml.EscapeForXML('a<![CDATA[b'), 'a&lt;![CDATA[b')
    self.assertEqual(kml.EscapeForXML('a]]>b'), 'a]]&gt;b')
    self.assertEqual(kml.EscapeForXML('</bye>'), '&lt;/bye&gt;')
    self.assertEqual(kml.EscapeForXML('<' * 100), '&lt;' * 100)
    self.assertNotEqual(kml.EscapeForXML('<' * 101), '&lt;' * 101)

  def testEscapeForXMLWithShortUTF8Strings(self):
    # 10 bytes as UTF8.
    test_string = u'\u043f\u043e\u0438\u0441\u043a'.encode('utf8')
    self.assertEqual(kml.EscapeForXML(test_string), test_string)
    self.assertEqual(kml.EscapeForXML(test_string + '>'), test_string + '&gt;')
    self.assertEqual(kml.EscapeForXML(test_string * 10), test_string * 10)
    self.assertNotEqual(kml.EscapeForXML(test_string * 11), test_string * 11)

  def testEscapeForXMLWithShortUnicodeStrings(self):
    test_string = u'\u043f\u043e\u0438\u0441\u043a'  # 10 bytes as UTF8.
    self.assertEqual(kml.EscapeForXML(test_string),
                     test_string.encode('utf8'))
    self.assertEqual(kml.EscapeForXML(test_string + u'>'),
                     test_string.encode('utf8') + '&gt;')
    self.assertEqual(kml.EscapeForXML(test_string * 10),
                     test_string.encode('utf8') * 10)
    self.assertNotEqual(kml.EscapeForXML(test_string * 11),
                        test_string.encode('utf8') * 11)

  def testEscapeForXMLWithSafeLongASCIIStrings(self):
    self.assertEqual(kml.EscapeForXML('x' * 101),
                     '<![CDATA[' + 'x' * 101 + ']]>')
    self.assertEqual(kml.EscapeForXML('abc' * 1000),
                     '<![CDATA[' + 'abc' * 1000 + ']]>')

  def testEscapeForXMLWithUnsafeLongASCIIStrings(self):
    self.assertEqual(kml.EscapeForXML('>' * 101),
                     '<![CDATA[' + '>' * 101 + ']]>')
    self.assertEqual(kml.EscapeForXML('a&c' * 1000),
                     '<![CDATA[' + 'a&c' * 1000 + ']]>')
    self.assertEqual(kml.EscapeForXML('a' * 100 + ']]>' + 'bc'),
                     '<![CDATA[' + 'a' * 100 + ']]]]><![CDATA[>' + 'bc' + ']]>')

  def testEscapeForXMLWithLongUTF8Strings(self):
    test_string = '\xd0\xbf\xd0\xbe\xd0\xb8\xd1\x81\xd0\xba'
    self.assertEqual(kml.EscapeForXML(test_string * 100),
                     '<![CDATA[' + test_string * 100 + ']]>')
    self.assertEqual(kml.EscapeForXML(test_string * 100 + ']]>' + test_string),
                     ('<![CDATA[' + test_string * 100 + ']]]]><![CDATA[>' +
                      test_string + ']]>'))

  def testEscapeForXMLWithLongUnicodeStrings(self):
    test_string = u'\u043f\u043e\u0438\u0441\u043a'  # 10 bytes as UTF8.
    self.assertEqual(kml.EscapeForXML(test_string * 100),
                     '<![CDATA[' + test_string.encode('utf8') * 100 + ']]>')
    self.assertEqual(kml.EscapeForXML(test_string * 100 + ']]>' + test_string),
                     ('<![CDATA[' + test_string.encode('utf8') * 100
                      + ']]]]><![CDATA[>' + test_string.encode('utf8') + ']]>'))

  def testEscapeForXMLFailsOnNonUTF8DecodableStrings(self):
    test_string = '\xef\xee\xe8\xf1\xea'  # Windows-1251 encoded, incompatible.
    self.assertRaises(UnicodeDecodeError, kml.EscapeForXML, test_string)
    self.assertRaises(UnicodeDecodeError, kml.EscapeForXML, test_string * 101)

  def testEscapeForXMLFailsOnNonStrings(self):
    self.assertRaises(TypeError, kml.EscapeForXML, 1)
    self.assertRaises(TypeError, kml.EscapeForXML, [])
    self.assertRaises(TypeError, kml.EscapeForXML, None)


class PageTemplateFunctionsTest(mox.MoxTestBase):

  FAKE_API_KEYS = {'a': 'ka', 'b': 'kb', 'a:123': 'kap'}

  def testInsertJSAPIKeyForHostAndPort(self):
    self.stubs.Set(settings, 'JS_API_KEYS', self.FAKE_API_KEYS)

    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'a', 'SERVER_PORT': '123'})
    self.assertEqual(pages.InsertJSAPIKey(), 'kap')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'a', 'SERVER_PORT': '999'})
    self.assertEqual(pages.InsertJSAPIKey(), 'ka')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'b', 'SERVER_PORT': '123'})
    self.assertEqual(pages.InsertJSAPIKey(), 'kb')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'c', 'SERVER_PORT': '123'})
    self.assertEqual(pages.InsertJSAPIKey(), '')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': '', 'SERVER_PORT': '123'})
    self.assertEqual(pages.InsertJSAPIKey(), '')

  def testInsertJSAPIKeyForHostOnly(self):
    self.stubs.Set(settings, 'JS_API_KEYS', self.FAKE_API_KEYS)

    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'a'})
    self.assertEqual(pages.InsertJSAPIKey(), 'ka')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'b'})
    self.assertEqual(pages.InsertJSAPIKey(), 'kb')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': 'c'})
    self.assertEqual(pages.InsertJSAPIKey(), '')
    self.stubs.Set(os, 'environ', {'SERVER_NAME': ''})
    self.assertEqual(pages.InsertJSAPIKey(), '')

  def testEscapeForScriptStringWithHarmlessStrings(self):
    self.assertEqual(pages.EscapeForScriptString(''), '')
    self.assertEqual(pages.EscapeForScriptString('abc'), 'abc')

  def testEscapeForScriptStringWithHarmfulStrings(self):
    self.assertEqual(pages.EscapeForScriptString('"'), r'\"')
    self.assertEqual(pages.EscapeForScriptString(r"""abc"\/'def"""),
                     r"""abc\"\\\/\'def""")
    self.assertEqual(pages.EscapeForScriptString(r"""</script>I'm out!"""),
                     r"""<\/script>I\'m out!""")

  def testEscapeForScriptStringWithNonStrignObjects(self):
    self.assertEqual(pages.EscapeForScriptString(None), '')
    self.assertEqual(pages.EscapeForScriptString(0), '0')
    self.assertEqual(pages.EscapeForScriptString(123), '123')
    self.assertEqual(pages.EscapeForScriptString(['/', 'a']),
                     r"""[\'\/\', \'a\']""")

  def testLookup(self):
    self.mox.StubOutWithMock(template.django.template, 'resolve_variable')
    template.django.template.resolve_variable('b', 'a').AndReturn('c')
    template.django.template.resolve_variable(1, None).AndReturn('d')
    self.mox.ReplayAll()
    self.assertEqual(pages.Lookup('a', 'b'), 'c')
    self.assertEqual(pages.Lookup(None, 1), 'd')
