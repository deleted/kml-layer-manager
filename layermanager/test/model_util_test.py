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

"""Small tests for utility functions related to the models."""


import datetime
import operator
from google.appengine.ext import db
from google.appengine.ext.webapp import template
from lib.geo import geomodel
from lib.mox import mox
import model
import util


class ModelUtilTest(mox.MoxTestBase):

  def testValidateDjangoTemplate(self):
    self.mox.StubOutWithMock(template, 'register_template_library')
    self.mox.StubOutWithMock(template, 'Template')
    dummy = object()
    error = template.django.template.TemplateSyntaxError()

    template.register_template_library('template_functions.entities')
    template.Template(dummy)
    template.register_template_library('template_functions.entities')
    template.Template(dummy).AndRaise(error)
    self.mox.ReplayAll()
    model._ValidateDjangoTemplate(dummy)
    self.assertRaises(db.BadValueError, model._ValidateDjangoTemplate, dummy)

  def testValidateKMLColor(self):
    model._ValidateKMLColor(None)
    model._ValidateKMLColor('12345678')
    model._ValidateKMLColor('12AABB08')
    model._ValidateKMLColor('12aabb78')
    model._ValidateKMLColor('1a4eB78f')
    self.assertRaises(db.BadValueError, model._ValidateKMLColor, '')
    self.assertRaises(db.BadValueError, model._ValidateKMLColor, '5678')
    self.assertRaises(db.BadValueError, model._ValidateKMLColor, '567855')
    self.assertRaises(db.BadValueError, model._ValidateKMLColor, '1234567g')
    self.assertRaises(db.BadValueError, model._ValidateKMLColor, '1234567f ')
    self.assertRaises(db.BadValueError, model._ValidateKMLColor, '012345678')
    self.assertRaises(db.BadValueError, model._ValidateKMLColor, '0x12345678')
    self.assertRaises(TypeError, model._ValidateKMLColor, 0x12345678)

  def testRenderKMLTemplateWithFilledCache(self):
    self.mox.StubOutWithMock(template, 'Context')
    mock_template = self.mox.CreateMockAnything()
    dummy_file = object()
    dummy_args = object()
    dummy_context = object()
    dummy_result = object()
    self.stubs.Set(model, '_kml_template_cache', {dummy_file: mock_template})

    template.Context(dummy_args).AndReturn(dummy_context)
    mock_template.render(dummy_context).AndReturn(dummy_result)
    self.mox.ReplayAll()
    self.assertEqual(model._RenderKMLTemplate(dummy_file, dummy_args),
                     dummy_result)

  def testRenderKMLTemplateWithEmptyCache(self):
    self.mox.StubOutWithMock(template, 'register_template_library')
    self.mox.StubOutWithMock(template, 'load')
    self.mox.StubOutWithMock(template, 'Context')
    mock_template = self.mox.CreateMockAnything()
    mock_cache = {}
    dummy_file = 'dummy'
    dummy_args = object()
    dummy_context = object()
    dummy_result = object()
    self.stubs.Set(model, '_kml_template_cache', mock_cache)

    template.register_template_library('template_functions.kml')
    template.load('kml_templates/dummy').AndReturn(mock_template)
    template.Context(dummy_args).AndReturn(dummy_context)
    mock_template.render(dummy_context).AndReturn(dummy_result)
    self.mox.ReplayAll()
    self.assertEqual(model._RenderKMLTemplate(dummy_file, dummy_args),
                     dummy_result)
    self.assertEqual(mock_cache[dummy_file], mock_template)


class LayerUtilTest(mox.MoxTestBase):

  def testGetResources(self):
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.resource_set = self.mox.CreateMockAnything()
    dummy_result = object()
    good_type = model.Resource.TYPES[0]
    bad_type = 'x' + ''.join(model.Resource.TYPES)  # Guaranteed invalid.
    mock_layer.resource_set.filter('type', good_type).AndReturn(dummy_result)
    self.mox.ReplayAll()
    self.assertEqual(model.Layer.GetResources(mock_layer, good_type),
                     dummy_result)
    self.assertRaises(ValueError, model.Layer.GetResources,
                      mock_layer, bad_type)

  def testIsPermitted(self):
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.permission_set = self.mox.CreateMockAnything()
    mock_filtered_permission_set = self.mox.CreateMockAnything()
    mock_permission = self.mox.CreateMockAnything()
    dummy_user = object()
    dummy_type = object()

    mock_layer.permission_set.filter('user', dummy_user).AndReturn(
        mock_filtered_permission_set)
    mock_filtered_permission_set.filter('type', dummy_type).AndReturn(
        mock_permission)
    mock_permission.get().AndReturn('dummy')

    mock_layer.permission_set.filter('user', dummy_user).AndReturn(
        mock_filtered_permission_set)
    mock_filtered_permission_set.filter('type', dummy_type).AndReturn(
        mock_permission)
    mock_permission.get().AndReturn(None)

    self.mox.ReplayAll()
    self.assertTrue(model.Layer.IsPermitted(mock_layer, dummy_user, dummy_type))
    self.assertFalse(model.Layer.IsPermitted(
        mock_layer, dummy_user, dummy_type))

  def testSafeDelete(self):
    self.mox.StubOutWithMock(db, 'run_in_transaction')
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.permission_set = self.mox.CreateMockAnything()

    db.run_in_transaction(mox.Func(lambda f: f() or True))
    mock_permissions = [self.mox.CreateMockAnything() for _ in xrange(5)]
    mock_layer.permission_set.ancestor(mock_layer).AndReturn(mock_permissions)
    for mock_permission in mock_permissions:
      mock_permission.delete()
    mock_layer.delete()

    self.mox.ReplayAll()
    model.Layer.SafeDelete(mock_layer)

  def testGetSortedContents(self):
    self.mox.StubOutWithMock(operator, 'attrgetter')
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.entity_set = self.mox.CreateMockAnything()
    mock_layer.link_set = self.mox.CreateMockAnything()
    mock_layer.folder_set = self.mox.CreateMockAnything()
    sorted_list = [(1, 'f'), (3, 'b'), (4, 'a'), (5, 'e'), (8, 'd'), (11, 'c')]

    mock_layer.entity_set.filter('folder', None).AndReturn(
        [(4, 'a'), (3, 'b')])
    mock_layer.link_set.filter('folder', None).AndReturn(
        [(11, 'c'), (8, 'd'), (5, 'e')])
    mock_layer.folder_set.filter('folder', None).AndReturn([(1, 'f')])
    operator.attrgetter('folder_index').AndReturn(lambda x: x[0])
    self.mox.ReplayAll()
    self.assertEqual(model.Layer.GetSortedContents(mock_layer), sorted_list)


class ResourceUtilTest(mox.MoxTestBase):

  def testGetURL(self):
    self.mox.StubOutWithMock(util, 'GetURL')
    mock_resource = self.mox.CreateMock(model.Resource)
    mock_resource.type = mock_resource.external_url = None
    mock_key = self.mox.CreateMockAnything()
    dummy_external_url = object()
    dummy_blob_url = object()

    mock_resource.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)

    mock_resource.key().AndReturn(mock_key)
    mock_key.id().AndReturn(43)

    mock_resource.key().AndReturn(mock_key)
    mock_key.id().AndReturn(44)

    mock_resource.key().AndReturn(mock_key)
    mock_key.id().AndReturn(45)

    mock_resource.key().AndReturn(mock_key)
    mock_key.id().AndReturn(46)
    util.GetURL('/serve/0/').AndReturn('dummy-absolute-url/')

    self.mox.ReplayAll()

    # Without an extension.
    mock_resource.filename = 'extensionless'
    self.assertEqual(model.Resource.GetURL(mock_resource), 'r42')

    # With an extension.
    mock_resource.filename = 'file.with_an_extension'
    self.assertEqual(model.Resource.GetURL(mock_resource),
                     'r43.with_an_extension')

    # A raw model, resulting in a predefined extension.
    mock_resource.type = 'model'
    self.assertEqual(model.Resource.GetURL(mock_resource), 'r44.dae')

    # A KMZ model with an internal path.
    mock_resource.type = 'model_in_kmz'
    mock_resource.filename = 'dummy-filename'
    self.assertEqual(model.Resource.GetURL(mock_resource),
                     'r45.kmz/dummy-filename')

    # With absolute URL.
    mock_resource.type = 'image'
    mock_resource.filename = 'file.with_another_extension'
    self.assertEqual(model.Resource.GetURL(mock_resource, absolute=True),
                     'dummy-absolute-url/r46.with_another_extension')

    # With external URL.
    mock_resource.external_url = dummy_external_url
    self.assertEqual(model.Resource.GetURL(mock_resource), dummy_external_url)

  def testGetThumbnailURL(self):
    self.mox.StubOutWithMock(util, 'GetURL')
    mock_resource = self.mox.CreateMock(model.Resource)
    dummy_external_url = object()

    mock_resource.GetURL().AndReturn('dummy-url')

    self.mox.ReplayAll()

    # Invalid type.
    mock_resource.type = 'model'
    self.assertRaises(TypeError, model.Resource.GetThumbnailURL,
                      mock_resource, 4)

    # External URL.
    mock_resource.type = 'image'
    mock_resource.external_url = dummy_external_url
    self.assertEqual(model.Resource.GetThumbnailURL(mock_resource, 8),
                     dummy_external_url)

    # Normal case.
    mock_resource.external_url = None
    self.assertEqual(model.Resource.GetThumbnailURL(mock_resource, 15),
                     'dummy-url?resize=15')


class FolderUtilTest(mox.MoxTestBase):

  def testGetSortedContents(self):
    self.mox.StubOutWithMock(operator, 'attrgetter')
    mock_folder = self.mox.CreateMock(model.Folder)
    mock_folder.entity_set = [(4, 'a'), (3, 'b')]
    mock_folder.link_set = [(11, 'c'), (8, 'd'), (5, 'e')]
    mock_folder.folder_set = [(1, 'f')]
    sorted_list = [(1, 'f'), (3, 'b'), (4, 'a'), (5, 'e'), (8, 'd'), (11, 'c')]

    operator.attrgetter('folder_index').AndReturn(lambda x: x[0])
    self.mox.ReplayAll()
    self.assertEqual(model.Folder.GetSortedContents(mock_folder), sorted_list)


class SchemaUtilTest(mox.MoxTestBase):

  def testSafeDelete(self):
    self.mox.StubOutWithMock(db, 'run_in_transaction')
    mock_schema = self.mox.CreateMock(model.Schema)
    mock_schema.field_set = self.mox.CreateMockAnything()
    mock_schema.template_set = self.mox.CreateMockAnything()

    db.run_in_transaction(mox.Func(lambda f: f() or True))
    mock_fields = [self.mox.CreateMockAnything() for _ in xrange(5)]
    mock_templates = [self.mox.CreateMockAnything() for _ in xrange(7)]
    mock_schema.field_set.ancestor(mock_schema).AndReturn(mock_fields)
    mock_schema.template_set.ancestor(mock_schema).AndReturn(mock_templates)
    for mock_field in mock_fields:
      mock_field.delete()
    for mock_template in mock_templates:
      mock_template.delete()
    mock_schema.delete()

    self.mox.ReplayAll()
    model.Schema.SafeDelete(mock_schema)


class TemplateUtilTest(mox.MoxTestBase):

  def testEvaluateWithFilledCache(self):
    mock_template = self.mox.CreateMock(model.Template)
    mock_template.schema = self.mox.CreateMockAnything()
    mock_field1 = self.mox.CreateMockAnything()
    mock_field1.name = 'a'
    mock_field2 = self.mox.CreateMockAnything()
    mock_field2.name = 'x'
    mock_template.schema.field_set = [mock_field1, mock_field2]
    mock_key = self.mox.CreateMockAnything()
    mock_compiled_template = self.mox.CreateMockAnything()
    mock_cache = {'entity_templates': {42: mock_compiled_template}}
    mock_entity = self.mox.CreateMockAnything()
    mock_entity.field_a = 'b'
    mock_entity.x = 'y'
    mock_entity.field_x = 'z'
    mock_entity.field_z = 'w'
    dummy_link_template = object()
    dummy_result = object()

    @mox.Func
    def VerifyArgs(args):
      args = args.dicts[0]
      self.assertEqual(set(args.keys()),
                       set(['entity', '_cache', '_link_template', 'x', 'a']))
      self.assertEqual(args['entity'], mock_entity)
      self.assertEqual(args['_cache'], mock_cache)
      self.assertEqual(args['_link_template'], dummy_link_template)
      self.assertEqual(args['x'], 'z')
      self.assertEqual(args['a'], 'b')
      return True

    mock_template.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)
    mock_compiled_template.render(VerifyArgs).AndReturn(dummy_result)

    self.mox.ReplayAll()
    result = model.Template.Evaluate(
        mock_template, mock_entity, mock_cache, dummy_link_template)
    self.assertEqual(result, dummy_result)

  def testEvaluateWithEmptyCacheAndUnicodeText(self):
    self.mox.StubOutWithMock(template, 'register_template_library')
    self.mox.StubOutWithMock(template, 'Template')
    mock_template = self.mox.CreateMock(model.Template)
    mock_template.text = u'\u043f\u043e\u0438\u0441\u043a'
    encoded_text = mock_template.text.encode('utf8')
    mock_template.schema = self.mox.CreateMockAnything()
    mock_template.schema.field_set = []
    mock_key = self.mox.CreateMockAnything()
    mock_compiled_template = self.mox.CreateMockAnything()
    mock_cache = {'entity_templates': {}}
    dummy_entity = object()
    dummy_result = object()

    @mox.Func
    def VerifyArgs(args):
      args = args.dicts[0]
      self.assertEqual(set(args.keys()),
                       set(['entity', '_cache', '_link_template']))
      self.assertEqual(args['entity'], dummy_entity)
      self.assertEqual(args['_cache'], mock_cache)
      self.assertEqual(args['_link_template'], None)
      return True

    mock_template.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)
    template.register_template_library('template_functions.entities')
    template.Template(encoded_text).AndReturn(mock_compiled_template)
    mock_compiled_template.render(VerifyArgs).AndReturn(dummy_result)

    self.mox.ReplayAll()
    result = model.Template.Evaluate(
        mock_template, dummy_entity, mock_cache)
    self.assertEqual(result, dummy_result)
    self.assertEqual(mock_cache['entity_templates'],
                     {42: mock_compiled_template})

  def testEvaluateWithNoCacheAndUTF8Text(self):
    self.mox.StubOutWithMock(template, 'register_template_library')
    self.mox.StubOutWithMock(template, 'Template')
    mock_template = self.mox.CreateMock(model.Template)
    mock_template.text = u'\u043f\u043e\u0438\u0441\u043a'.encode('utf8')
    mock_template.schema = self.mox.CreateMockAnything()
    mock_template.schema.field_set = []
    mock_key = self.mox.CreateMockAnything()
    mock_compiled_template = self.mox.CreateMockAnything()
    dummy_entity = object()
    dummy_result = object()

    @mox.Func
    def VerifyArgs(args):
      args = args.dicts[0]
      self.assertEqual(set(args.keys()),
                       set(['entity', '_cache', '_link_template']))
      self.assertEqual(args['entity'], dummy_entity)
      self.assertEqual(args['_cache'], None)
      self.assertEqual(args['_link_template'], None)
      return True

    mock_template.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)
    template.register_template_library('template_functions.entities')
    template.Template(mock_template.text).AndReturn(mock_compiled_template)
    mock_compiled_template.render(VerifyArgs).AndReturn(dummy_result)

    self.mox.ReplayAll()
    result = model.Template.Evaluate(mock_template, dummy_entity)
    self.assertEqual(result, dummy_result)


class FieldUtilTest(mox.MoxTestBase):

  def testValidateString(self):
    mock_schema = mox.Mox().CreateMock(model.Schema)  # Skip verification.
    field = model.Field(schema=mock_schema, name='a', type='string')

    self.assertEqual(field.Validate(''), u'')
    self.assertEqual(field.Validate('hello'), u'hello')
    self.assertEqual(field.Validate(u'\u043e'), u'\u043e')
    self.assertEqual(field.Validate(u'\u043e'.encode('utf8')), u'\u043e')
    self.assertEqual(field.Validate('a' * 999999), u'a' * 999999)

    self.assertEqual(field.Validate(None), None)
    self.assertEqual(field.Validate(1), None)
    self.assertEqual(field.Validate(['a', 'b']), None)
    # Windows-1251 encoding is incompatible with UTF-8.
    self.assertEqual(field.Validate(u'\u043e'.encode('1251')), None)

  def testValidateText(self):
    mock_schema = mox.Mox().CreateMock(model.Schema)  # Skip verification.
    field = model.Field(schema=mock_schema, name='a', type='text')

    self.assertEqual(field.Validate(''), db.Text(u''))
    self.assertEqual(field.Validate('hello'), db.Text(u'hello'))
    self.assertEqual(field.Validate(u'\u043e'), db.Text(u'\u043e'))
    self.assertEqual(field.Validate(u'\u043e'.encode('utf8')),
                     db.Text(u'\u043e'))
    self.assertEqual(field.Validate('a' * 999999), db.Text(u'a' * 999999))

    self.assertEqual(field.Validate(None), None)
    self.assertEqual(field.Validate(1), None)
    self.assertEqual(field.Validate(['a', 'b']), None)
    # Windows-1251 encoding is incompatible with UTF-8.
    self.assertEqual(field.Validate(u'\u043e'.encode('1251')), None)

  def testValidateInteger(self):
    mock_schema = mox.Mox().CreateMock(model.Schema)  # Skip verification.
    field = model.Field(schema=mock_schema, name='a', type='integer')

    self.assertEqual(field.Validate(1), 1)
    self.assertEqual(field.Validate(2.3), 2)
    self.assertEqual(field.Validate(-3), -3)
    self.assertEqual(field.Validate(4L), 4)
    self.assertEqual(field.Validate('5'), 5)
    self.assertEqual(field.Validate('-6'), -6)

    self.assertEqual(field.Validate(None), None)
    self.assertEqual(field.Validate(''), None)
    self.assertEqual(field.Validate('7.8'), None)
    self.assertEqual(field.Validate('-9.0'), None)
    self.assertEqual(field.Validate('1a'), None)
    self.assertEqual(field.Validate(complex(1, 2)), None)

  def testValidateFloat(self):
    mock_schema = mox.Mox().CreateMock(model.Schema)  # Skip verification.
    field = model.Field(schema=mock_schema, name='a', type='float')

    self.assertEqual(field.Validate(1), 1.0)
    self.assertEqual(field.Validate(2.3), 2.3)
    self.assertEqual(field.Validate(-3), -3.0)
    self.assertEqual(field.Validate(-4.56), -4.56)
    self.assertEqual(field.Validate(7L), 7.0)
    self.assertEqual(field.Validate('5'), 5.0)
    self.assertEqual(field.Validate('-6'), -6.0)
    self.assertEqual(field.Validate('7.8'), 7.8)
    self.assertEqual(field.Validate('-9.0'), -9.0)
    self.assertEqual(field.Validate('+1.23E-4'), 1.23E-4)

    self.assertEqual(field.Validate(None), None)
    self.assertEqual(field.Validate(''), None)
    self.assertEqual(field.Validate('1a'), None)
    self.assertEqual(field.Validate(complex(1, 2)), None)

  def testValidateDate(self):
    mock_schema = mox.Mox().CreateMock(model.Schema)  # Skip verification.
    field = model.Field(schema=mock_schema, name='a', type='date')

    self.assertEqual(field.Validate('2010-1-2'),
                     datetime.datetime(2010, 1, 2))
    self.assertEqual(field.Validate('2005-03-04'),
                     datetime.datetime(2005, 3, 4))
    self.assertEqual(field.Validate('1000-6-7'),
                     datetime.datetime(1000, 6, 7))
    self.assertEqual(field.Validate('9999-8-9'),
                     datetime.datetime(9999, 8, 9))
    self.assertEqual(field.Validate('2004-2-29'),
                     datetime.datetime(2004, 2, 29))  # Leap year.

    self.assertEqual(field.Validate('2004-8-15 16:23:42'),
                     datetime.datetime(2004, 8, 15, 16, 23, 42))

    self.assertEqual(field.Validate(''), None)
    self.assertEqual(field.Validate('dummy'), None)
    self.assertEqual(field.Validate(1234567890), None)
    self.assertEqual(field.Validate(' 2004-8-15'), None)
    self.assertEqual(field.Validate('2004-8-15junk'), None)
    self.assertEqual(field.Validate('2004-88-15'), None)
    self.assertEqual(field.Validate('2005-2-29'), None)  # Non-leap year.
    self.assertEqual(field.Validate('2004-8-15T16:23:42'), None)
    self.assertEqual(field.Validate('2004-8-15 16:99:42'), None)

  def testValidateColor(self):
    self.mox.StubOutWithMock(model, '_ValidateKMLColor')
    mock_schema = mox.Mox().CreateMock(model.Schema)  # Skip verification.
    field = model.Field(schema=mock_schema, name='a', type='color')
    bad_color = object()

    model._ValidateKMLColor('MiXeDcAsE')
    model._ValidateKMLColor(bad_color).AndRaise(ValueError)

    self.mox.ReplayAll()
    self.assertEqual(field.Validate('MiXeDcAsE'), 'mixedcase')
    self.assertEqual(field.Validate(bad_color), None)

  def testValidateResource(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    mock_schema = mox.Mox().CreateMock(model.Schema)  # Skip verification.
    mock_schema.layer = object()
    mock_resource = self.mox.CreateMockAnything()
    field = model.Field(schema=mock_schema, name='a', type='resource')
    image_value = object()
    nonexistent_value = object()

    util.GetInstance(model.Resource, image_value, mock_schema.layer,
                     required=False).AndReturn(mock_resource)
    util.GetInstance(model.Resource, nonexistent_value, mock_schema.layer,
                     required=False).AndRaise(util.BadRequest)

    self.mox.ReplayAll()
    self.assertEqual(field.Validate(image_value), image_value)
    self.assertEqual(field.Validate(nonexistent_value), None)


class EntityUtilTest(mox.MoxTestBase):

  def testSafeDelete(self):
    self.mox.StubOutWithMock(db, 'run_in_transaction')
    self.mox.StubOutWithMock(model, 'Geometry')
    mock_entity = self.mox.CreateMock(model.Entity)
    mock_entity.geometries = [4, 8, 15]
    mock_geometries = [self.mox.CreateMockAnything() for _ in xrange(3)]

    db.run_in_transaction(mox.Func(lambda f: f() or True))

    model.Geometry.get_by_id(4, parent=mock_entity).AndReturn(
        mock_geometries[0])
    model.Geometry.get_by_id(8, parent=mock_entity).AndReturn(
        mock_geometries[1])
    model.Geometry.get_by_id(15, parent=mock_entity).AndReturn(
        mock_geometries[2])
    mock_geometries[0].delete()
    mock_geometries[1].delete()
    mock_geometries[2].delete()
    mock_entity.delete()

    self.mox.ReplayAll()
    model.Entity.SafeDelete(mock_entity)

  def testUpdateLocation(self):
    self.mox.StubOutWithMock(geomodel, 'GeoModel')
    self.mox.StubOutWithMock(model, 'Geometry')
    mock_entity = self.mox.CreateMock(model.Entity)
    mock_entity.geometries = [4, 8, 15]
    mock_geometry = self.mox.CreateMockAnything()
    mock_custom_geometry = self.mox.CreateMockAnything()
    dummy_center = object()
    dummy_custom_center = object()

    mock_custom_geometry.GetCenter().AndReturn(dummy_custom_center)
    geomodel.GeoModel.update_location(mock_entity)

    model.Geometry.get_by_id(4, parent=mock_entity).AndReturn(mock_geometry)
    mock_geometry.GetCenter().AndReturn(dummy_center)
    geomodel.GeoModel.update_location(mock_entity)

    self.mox.ReplayAll()

    # Custom geometry.
    model.Entity.UpdateLocation(mock_entity, mock_custom_geometry)
    self.assertEqual(mock_entity.location, dummy_custom_center)

    # Normal operation.
    model.Entity.UpdateLocation(mock_entity)
    self.assertEqual(mock_entity.location, dummy_center)

    # No geometries.
    mock_entity.geometries = []
    self.assertRaises(ValueError, model.Entity.UpdateLocation, mock_entity)


class GeometryCenterCalculationTest(mox.MoxTestBase):
  # Testing with real numbers here is far from perfect, but I see no way to
  # mock, record and verify operator applications using mox without huge amounts
  # of hackery.

  def testPointGetCenter(self):
    mock_point = mox.Mox().CreateMock(model.Point)  # Skip verification.
    dummy_center = object()
    mock_point.location = dummy_center
    self.assertEqual(model.Point.GetCenter(mock_point), dummy_center)

  def testLineStringGetCenter(self):
    line_string = model.LineString(points=[db.GeoPt(1.23, 4.56)])
    self.assertEqual(line_string.GetCenter(), db.GeoPt(1.23, 4.56))

    points = [db.GeoPt(1, 50), db.GeoPt(7, 40), db.GeoPt(5, 90)]
    line_string = model.LineString(points=points)
    self.assertEqual(line_string.GetCenter(), db.GeoPt(13.0 / 3, 180.0 / 3))

    line_string = model.LineString(points=[])
    self.assertRaises(ZeroDivisionError, line_string.GetCenter)

  def testPolygonGetCenter(self):
    polygon = model.Polygon(outer_points=[db.GeoPt(5.6, 7.8)])
    self.assertEqual(polygon.GetCenter(), db.GeoPt(5.6, 7.8))

    points = [db.GeoPt(1, 50), db.GeoPt(7, 40), db.GeoPt(5, 90)]
    polygon = model.Polygon(outer_points=points)
    self.assertEqual(polygon.GetCenter(), db.GeoPt(13.0 / 3, 180.0 / 3))

    polygon = model.Polygon(outer_points=[])
    self.assertRaises(ZeroDivisionError, polygon.GetCenter)

  def testModelGetCenter(self):
    mock_model = mox.Mox().CreateMock(model.Model)  # Skip verification.
    dummy_center = object()
    mock_model.location = dummy_center
    self.assertEqual(model.Model.GetCenter(mock_model), dummy_center)

  def testGroundOverlayGetCenter(self):
    mock_image = mox.Mox().CreateMock(model.Resource)  # Skip verification.

    overlay = model.GroundOverlay(north=100.0, south=10.0, east=200.0, west=6.0,
                                  image=mock_image)
    self.assertEqual(overlay.GetCenter(), db.GeoPt(55, 103))

    overlay = model.GroundOverlay(north=100.0, south=-10.0, east=0.0, west=-6.0,
                                  image=mock_image, is_quad=False)
    self.assertEqual(overlay.GetCenter(), db.GeoPt(45, -3))

    # Non-uniform.
    overlay = model.GroundOverlay(is_quad=True, image=mock_image,
                                  corners=[db.GeoPt(-1, -3), db.GeoPt(-1, 1),
                                           db.GeoPt(2, 1), db.GeoPt(4, -2)])
    self.assertEqual(overlay.GetCenter(), db.GeoPt(1.0, -0.75))

  def testPhotoOverlayGetCenter(self):
    mock_overlay = mox.Mox().CreateMock(model.PhotoOverlay)  # No verification.
    dummy_center = object()
    mock_overlay.location = dummy_center
    self.assertEqual(model.PhotoOverlay.GetCenter(mock_overlay), dummy_center)
