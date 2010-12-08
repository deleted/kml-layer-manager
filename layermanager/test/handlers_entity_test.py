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

"""Medium tests for the Entity handler."""


import StringIO
from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.ext import db
from handlers import base
from handlers import entity
from lib.mox import mox
import model
import util


class EntityBalloonHandlerTest(mox.MoxTestBase):

  def testShowRaw(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = entity.EntityBalloonHandler()
    handler._cache = object()
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.dynamic_balloons = True
    mock_entity = self.mox.CreateMock(model.Entity)
    mock_entity.template = self.mox.CreateMockAnything()
    handler.request = {'id': 'id123', 'link_template': 'dummy-template'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    dummy_id = object()

    util.GetInstance(model.Entity, '123', mock_layer).AndReturn(mock_entity)

    util.GetInstance(model.Entity, '123', mock_layer).AndReturn(mock_entity)
    mock_entity.template.Evaluate(
        mock_entity, False, handler._cache, 'dummy-template').AndReturn(
            'dummy-result')
    handler.response.out.write('dummy-result')

    util.GetInstance(model.Entity, '123', mock_layer).AndReturn(mock_entity)

    self.mox.ReplayAll()

    # Success.
    handler.ShowRaw(mock_layer)

    # Layer should not serve dynamic balloons.
    mock_layer.dynamic_balloons = False
    self.assertRaises(util.BadRequest, handler.ShowRaw, mock_layer)

    # Entity has no template.
    mock_layer.dynamic_balloons = True
    mock_entity.template = None
    self.assertRaises(util.BadRequest, handler.ShowRaw, mock_layer)


class EntityHandlerTest(mox.MoxTestBase):

  def testDelete(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = entity.EntityHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_entity = self.mox.CreateMock(model.Entity)
    mock_layer = self.mox.CreateMockAnything()
    dummy_id = object()

    mock_layer.ClearCache()
    handler.request.get('entity_id').AndReturn(dummy_id)
    util.GetInstance(model.Entity, dummy_id, mock_layer).AndReturn(mock_entity)
    mock_entity.SafeDelete()

    handler.request.get('entity_id').AndReturn(dummy_id)
    util.GetInstance(model.Entity, dummy_id, mock_layer).AndRaise(
        util.BadRequest)

    self.mox.ReplayAll()
    handler.Delete(mock_layer)
    self.assertRaises(util.BadRequest, handler.Delete, mock_layer)

  def testCreate(self):
    self.mox.StubOutWithMock(entity, '_ValidateEntityArguments')
    self.mox.StubOutWithMock(entity, '_CreateEntityAndGeometry')
    self.mox.StubOutWithMock(model, 'Entity', use_mock_anything=True)
    handler = entity.EntityHandler()
    request = {'a': 'b', 'c': 'd', 'e': 'f'}
    handler.request = self.mox.CreateMockAnything()
    handler.request.get = request.get
    handler.request.arguments = request.keys
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()
    mock_entity = self.mox.CreateMockAnything()
    mock_layer = self.mox.CreateMockAnything()
    dummy_fields = object()
    dummy_geometries = object()
    dummy_id = object()

    # Success.
    entity._ValidateEntityArguments(mock_layer, request, False).AndReturn((
        dummy_fields, dummy_geometries))
    mock_layer.ClearCache()
    entity._CreateEntityAndGeometry(
        mock_layer, dummy_fields, dummy_geometries).AndReturn(dummy_id)
    handler.response.out.write(dummy_id)
    model.Entity.get_by_id(dummy_id).AndReturn(mock_entity)
    mock_entity.GenerateKML()

    # Failure during validation.
    entity._ValidateEntityArguments(mock_layer, request, False).AndRaise(
        util.BadRequest)

    # Failure during creation.
    entity._ValidateEntityArguments(mock_layer, request, False).AndReturn((
        dummy_fields, dummy_geometries))
    mock_layer.ClearCache()
    entity._CreateEntityAndGeometry(
        mock_layer, dummy_fields, dummy_geometries).AndRaise(util.BadRequest)

    self.mox.ReplayAll()
    handler.Create(mock_layer)
    self.assertRaises(util.BadRequest, handler.Create, mock_layer)
    self.assertRaises(util.BadRequest, handler.Create, mock_layer)

  def testBulkCreateFailure(self):
    handler = entity.EntityHandler()
    handler.request = {'entities': 'invalid-json'}
    self.assertRaises(util.BadRequest, handler.BulkCreate, None)

  def testBulkCreateSuccess(self):
    handler = entity.EntityHandler()
    handler.request = {'entities': '["123", "456", "789"]'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()
    mock_layer = self.mox.CreateMockAnything()
    dummy_fields = object()
    dummy_id = object()

    raw_inputs = []
    validated_fields = []

    def MockValidate(*args):
      raw_inputs.append(args)
      return 'field_' + args[1], 'geometries_' + args[1]
    self.stubs.Set(entity, '_ValidateEntityArguments', MockValidate)

    def MockCreate(*args):
      validated_fields.append(args)
      return int('999' + args[1][-3:])
    self.stubs.Set(entity, '_CreateEntityAndGeometry', MockCreate)

    mock_layer.ClearCache()

    self.mox.ReplayAll()
    handler.BulkCreate(mock_layer)
    self.assertEqual(raw_inputs, [(mock_layer, '123', False),
                                  (mock_layer, '456', False),
                                  (mock_layer, '789', False)])
    self.assertEqual(validated_fields,
                     [(mock_layer, 'field_123', 'geometries_123'),
                      (mock_layer, 'field_456', 'geometries_456'),
                      (mock_layer, 'field_789', 'geometries_789')])
    self.assertEqual(handler.response.out.getvalue(), '999123,999456,999789\n')

  def testBulkCreateInterrupt(self):
    handler = entity.EntityHandler()
    handler.request = {'entities': '["123", "456", "789"]'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()
    mock_layer = self.mox.CreateMockAnything()
    dummy_fields = object()
    dummy_id = object()

    raw_inputs = []
    validated_fields = []

    def MockValidate(*args):
      if args[1] == '789': raise runtime.DeadlineExceededError()
      raw_inputs.append(args)
      return 'field_' + args[1], 'geometries_' + args[1]
    self.stubs.Set(entity, '_ValidateEntityArguments', MockValidate)

    def MockCreate(*args):
      validated_fields.append(args)
      return int('999' + args[1][-3:])
    self.stubs.Set(entity, '_CreateEntityAndGeometry', MockCreate)

    mock_layer.ClearCache()

    self.mox.ReplayAll()
    handler.BulkCreate(mock_layer)
    self.assertEqual(raw_inputs, [(mock_layer, '123', False),
                                  (mock_layer, '456', False)])
    self.assertEqual(validated_fields,
                     [(mock_layer, 'field_123', 'geometries_123'),
                      (mock_layer, 'field_456', 'geometries_456')])
    self.assertEqual(handler.response.out.getvalue(),
                     '999123,999456\nRan out of time.')

  def testShowForm(self):
    self.mox.StubOutWithMock(base.PageHandler, 'ShowRaw')
    self.mox.StubOutWithMock(entity, '_GetGeometriesDescription')
    layer = model.Layer(name='a', world='earth')
    layer.put()
    entity1 = model.Entity(layer=layer, name='b', field_c='d')
    entity1.put().id()
    entity2 = model.Entity(layer=layer, name='e', field_f='g')
    entity2.put().id()
    geometries1 = [{'type': 'x', 'value': 'y'}, {'type': 'z', 'u': 'v', 'w': 5}]
    geometries2 = []
    handler = entity.EntityHandler()

    entity._GetGeometriesDescription(mox.IgnoreArg()).AndReturn(
        geometries1)
    entity._GetGeometriesDescription(mox.IgnoreArg()).AndReturn(
        geometries2)

    self.mox.ReplayAll()
    result = handler.ShowForm(layer)
    self.assertEqual(result.keys(), ['entities'])
    self.assertEqual(len(result['entities']), 2)
    self.assertEqual(result['entities'][0].geometry_objects, [{
        'type': 'x',
        'fields': json.dumps({'value': 'y'})
    }, {
        'type': 'z',
        'fields': json.dumps({'u': 'v', 'w': 5})
    }])
    self.assertEqual(result['entities'][1].geometry_objects, None)

  def testShowRaw(self):
    self.mox.StubOutWithMock(base.PageHandler, 'ShowRaw')
    self.mox.StubOutWithMock(entity, '_GetGeometriesDescription')
    layer = model.Layer(name='a', world='earth')
    layer.put()
    entity_object = model.Entity(layer=layer, name='b', field_c='d')
    entity_id = entity_object.put().id()
    dummy_geometries = object()
    handler = entity.EntityHandler()
    handler.request = {'id': str(entity_id)}

    entity._GetGeometriesDescription(mox.IgnoreArg()).AndReturn(
        dummy_geometries)
    base.PageHandler.ShowRaw(handler, layer, field_c='d',
                             geometries=dummy_geometries)

    self.mox.ReplayAll()
    handler.ShowRaw(layer)

  def testGetGeometriesDescription(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, type='model', external_url='/there',
                              filename='test')
    resource_id = resource.put().id()
    entity_object = model.Entity(layer=layer, name='b')
    entity_object.put()
    polygon = model.Polygon(outer_points=[db.GeoPt(12, 34), db.GeoPt(56, 78)],
                            parent=entity_object)
    polygon_id = polygon.put().id()
    model_object = model.Model(model=resource, location=db.GeoPt(90, 17),
                               altitude=35.0, altitude_mode='absolute',
                               parent=entity_object)
    model_id = model_object.put().id()
    entity_object.geometries = [polygon_id, model_id]
    entity_object.put().id()

    self.assertEqual(entity._GetGeometriesDescription(entity_object), [
        {'type': 'Polygon', 'outer_points': [[12.0, 34.0], [56.0, 78.0]],
         'extrude': None, 'altitude_mode': None, 'inner_altitudes': [],
         'outer_altitudes': [], 'inner_points': [], 'tessellate': None},
        {'type': 'Model', 'model': resource_id, 'location': [90.0, 17.0],
         'resource_alias_sources': [], 'resource_alias_targets': [],
         'tilt': None, 'heading': None, 'roll': None, 'altitude': 35.0,
         'altitude_mode': u'absolute', 'scale_x': None, 'scale_y': None,
         'scale_z': None}
    ])

  def testUpdate(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    self.mox.StubOutWithMock(entity, '_ValidateEntityArguments')
    self.mox.StubOutWithMock(entity, '_UpdateEntityAndGeometry')
    self.mox.StubOutWithMock(model, 'Entity', use_mock_anything=True)
    handler = entity.EntityHandler()
    request = {'a': 'b', 'c': 'd', 'entity_id': '123'}
    handler.request = self.mox.CreateMockAnything()
    handler.request.get = request.get
    handler.request.arguments = request.keys
    fields = {'x': 'y'}
    mock_entity = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_geometries = object()

    # Success.
    util.GetInstance(model.Entity, '123', dummy_layer).AndReturn(mock_entity)
    entity._ValidateEntityArguments(dummy_layer, request, True).AndReturn((
        fields, dummy_geometries))
    mock_entity.ClearCache()
    entity._UpdateEntityAndGeometry(123, fields, dummy_geometries, True)
    model.Entity.get_by_id(123).AndReturn(mock_entity)
    mock_entity.GenerateKML()

    # Failure during validation.
    util.GetInstance(model.Entity, '123', dummy_layer).AndReturn(mock_entity)
    entity._ValidateEntityArguments(dummy_layer, request, True).AndRaise(
        util.BadRequest)

    # Failure during geometry switch.
    util.GetInstance(model.Entity, '123', dummy_layer).AndReturn(mock_entity)
    entity._ValidateEntityArguments(dummy_layer, request, True).AndReturn((
        fields, dummy_geometries))
    mock_entity.ClearCache()
    entity._UpdateEntityAndGeometry(
        123, fields, dummy_geometries, True).AndRaise(db.BadValueError)

    self.mox.ReplayAll()
    handler.Update(dummy_layer)
    self.assertRaises(util.BadRequest, handler.Update, dummy_layer)
    self.assertRaises(util.BadRequest, handler.Update, dummy_layer)


class EntityUtilTest(mox.MoxTestBase):

  def testCreateEntityAndGeometry(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    schema = model.Schema(layer=layer, name='abc')
    schema.put()
    template = model.Template(schema=schema, name='def', text='', parent=schema)
    template_id = template.put().id()
    fields = {'name': 'ghi', 'view_location': db.GeoPt(1, 2),
              'template': template, 'field_x': 'y'}
    geometries = [
        {'type': model.Point, 'fields': {'location': db.GeoPt(3, 4)}},
        {'type': model.LineString, 'fields': {
            'points': [db.GeoPt(5, 6), db.GeoPt(7, 8)]
        }}
    ]

    entity_id = entity._CreateEntityAndGeometry(layer, fields, geometries)
    result = model.Entity.get_by_id(entity_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'ghi')
    self.assertEqual(result.view_location, db.GeoPt(1, 2))
    self.assertEqual(result.template.key().id(), template_id)
    self.assertEqual(result.field_x, 'y')
    self.assertEqual(len(result.geometries), 2)
    point = model.Geometry.get_by_id(result.geometries[0], parent=result)
    line_string = model.Geometry.get_by_id(result.geometries[1], parent=result)
    self.assertEqual(point.location, db.GeoPt(3, 4))
    self.assertEqual(line_string.points, [db.GeoPt(5, 6), db.GeoPt(7, 8)])
    self.assertEqual(result.location, db.GeoPt(3, 4))

  def testUpdateEntityAndGeometry(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    schema1 = model.Schema(layer=layer, name='abc')
    schema1.put()
    template1 = model.Template(schema=schema1, name='def', text='',
                               parent=schema1)
    template1.put()
    schema2 = model.Schema(layer=layer, name='abc2')
    schema2.put()
    template2 = model.Template(schema=schema2, name='def2', text='',
                               parent=schema2)
    template2_id = template2.put().id()
    old_entity = model.Entity(layer=layer, name='old', template=template1,
                              field_q='w')
    entity_id = old_entity.put().id()
    old_point = model.Point(location=db.GeoPt(6, 5), parent=old_entity)
    old_entity.geometries = [old_point.put().id()]
    old_entity.put()

    fields = {'name': 'ghi', 'view_location': db.GeoPt(1, 2),
              'template': template2, 'field_x': 'y'}
    geometries = [
        {'type': model.Point, 'fields': {'location': db.GeoPt(3, 4)}},
        {'type': model.LineString, 'fields': {
            'points': [db.GeoPt(5, 6), db.GeoPt(7, 8)]
        }}
    ]

    entity._UpdateEntityAndGeometry(entity_id, fields, geometries, True)
    result = model.Entity.get_by_id(entity_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'ghi')
    self.assertEqual(result.view_location, db.GeoPt(1, 2))
    self.assertEqual(result.template.key().id(), template2_id)
    self.assertEqual(result.field_x, 'y')
    self.assertFalse(hasattr(result, 'field_q'))
    self.assertEqual(len(result.geometries), 2)
    point = model.Geometry.get_by_id(result.geometries[0], parent=result)
    line_string = model.Geometry.get_by_id(result.geometries[1], parent=result)
    self.assertEqual(point.location, db.GeoPt(3, 4))
    self.assertEqual(line_string.points, [db.GeoPt(5, 6), db.GeoPt(7, 8)])
    self.assertEqual(result.location, db.GeoPt(3, 4))

  def testPrepareGeometryFields(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    image = model.Resource(layer=layer, type='image', external_url='x',
                           filename='y')
    image_id = image.put().id()
    model_object = model.Resource(layer=layer, type='model', external_url='z',
                                  filename='w')
    model_id = model_object.put().id()

    # Point.
    self.assertEqual(entity._PrepareGeometryFields('Point', {
        'location': [1.2, 3.4],
        'altitude': 5.6,
        'altitude_mode': 'absolute'
    }, layer), {
        'location': db.GeoPt(1.2, 3.4),
        'altitude': 5.6,
        'altitude_mode': 'absolute',
        'extrude': False
    })

    # LineString.
    self.assertEqual(entity._PrepareGeometryFields('LineString', {
        'points': [[1.2, 3.4], [1.25, 3.45]],
        'altitudes': [5.6, 6.7],
        'extrude': 'yes',
        'tessellate': False
    }, layer), {
        'points': [db.GeoPt(1.2, 3.4), db.GeoPt(1.25, 3.45)],
        'altitudes': [5.6, 6.7],
        'altitude_mode': None,
        'extrude': True,
        'tessellate': False
    })

    # Model.
    result = entity._PrepareGeometryFields('Model', {
        'location': [1.2, 3.4],
        'altitude': 5.6,
        'altitude_mode': 'absolute',
        'model': model_id,
        'heading': 6.7,
        'tilt': 7.8,
        'scale_x': 8.9,
        'scale_y': 9.0,
        'scale_z': 0.1,
        'resource_alias_sources': ['hello.jpg'],
        'resource_alias_targets': [image_id]
    }, layer)
    self.assertEqual(len(result['resource_alias_targets']), 1)
    self.assertEqual(result['resource_alias_targets'][0].key().id(), image_id)
    del result['resource_alias_targets']
    self.assertEqual(result['model'].key().id(), model_id)
    del result['model']
    self.assertEqual(result, {
        'location': db.GeoPt(1.2, 3.4),
        'altitude': 5.6,
        'altitude_mode': 'absolute',
        'heading': 6.7,
        'tilt': 7.8,
        'roll': None,
        'scale_x': 8.9,
        'scale_y': 9.0,
        'scale_z': 0.1,
        'resource_alias_sources': ['hello.jpg']
    })

    # Uniform GroundOverlay.
    result = entity._PrepareGeometryFields('GroundOverlay', {
        'image': image_id,
        'color': 'AABBCCDD',
        'draw_order': -13,
        'north': 4,
        'south': 8,
        'west': 15,
        'east': 16,
        'altitude': 23,
        'altitude_mode': 'random-value',
        'rotation': 42
    }, layer)
    self.assertEqual(result['image'].key().id(), image_id)
    del result['image']
    self.assertEqual(result, {
        'color': 'AABBCCDD',
        'draw_order': -13,
        'north': 4,
        'south': 8,
        'west': 15,
        'east': 16,
        'altitude': 23,
        'altitude_mode': 'random-value',
        'rotation': 42,
        'is_quad': False,
    })

    # Non-uniform GroundOverlay.
    result = entity._PrepareGeometryFields('GroundOverlay', {
        'image': image_id,
        'color': 'AABBCCDD',
        'draw_order': -52,
        'altitude': 66,
        'altitude_mode': 'random-value',
        'is_quad': True,
        'corners': [[1.2, 2.3], [3.4, 4.5], [5.6, 6.7], [7.8, 8.9]]
    }, layer)
    self.assertEqual(result['image'].key().id(), image_id)
    del result['image']
    self.assertEqual(result, {
        'color': 'AABBCCDD',
        'draw_order': -52,
        'altitude': 66,
        'altitude_mode': 'random-value',
        'is_quad': True,
        'corners': [db.GeoPt(1.2, 2.3), db.GeoPt(3.4, 4.5),
                    db.GeoPt(5.6, 6.7), db.GeoPt(7.8, 8.9)]
    })

  def testValidateEntityArguments(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    folder = model.Folder(layer=layer, name='abc')
    folder_id = folder.put().id()
    style = model.Style(layer=layer, name='def')
    style_id = style.put().id()
    region = model.Region(layer=layer, north=4.0, south=3.0, east=2.0, west=1.0)
    region_id = region.put().id()
    schema = model.Schema(layer=layer, name='ghi')
    schema_id = schema.put().id()
    template = model.Template(schema=schema, name='jkl', text='', parent=schema)
    template_id = template.put().id()

    # Success, full.
    fields, geometries = entity._ValidateEntityArguments(layer, {
        'name': 'abc',
        'snippet': 'def',
        'folder': str(folder_id),
        'folder_index': '123',
        'schema': str(schema_id),
        'template': str(template_id),
        'style': str(style_id),
        'region': str(region_id),
        'view_latitude': '4.5',
        'view_longitude': '5.6',
        'view_altitude': '6.7',
        'view_heading': '7.8',
        'view_tilt': '8.9',
        'view_roll': '12.34',
        'view_range': '9.0',
        'view_is_camera': 'yes',
        'priority': '42.13',
        'geometries': '[{"type":"Point","fields":{"location":[1.23,4.56]}}]'
    }, False)
    self.assertEqual(fields['folder'].key().id(), folder_id)
    del fields['folder']
    self.assertEqual(fields['template'].key().id(), template_id)
    del fields['template']
    self.assertEqual(fields['style'].key().id(), style_id)
    del fields['style']
    self.assertEqual(fields['region'].key().id(), region_id)
    del fields['region']
    self.assertEqual(fields, {
        'name': 'abc',
        'snippet': 'def',
        'folder_index': 123,
        'view_location': db.GeoPt(4.5, 5.6),
        'view_altitude': 6.7,
        'view_heading': 7.8,
        'view_tilt': 8.9,
        'view_roll': 12.34,
        'view_range': 9.0,
        'view_is_camera': True,
        'priority': 42.13
    })
    self.assertEqual(geometries, [
        {'type': model.Point, 'fields': {
            'location': db.GeoPt(1.23, 4.56), 'extrude': False,
            'altitude_mode': None, 'altitude': None,
        }}
    ])

    # Success, partial.
    fields, geometries = entity._ValidateEntityArguments(layer, {
        'name': 'abc',
        'folder': str(folder_id),
        'view_latitude': '4.5',
        'view_longitude': '5.6',
        'view_is_camera': '',
        'geometries': '[{"type":"LineString","fields":{"points":[[1.2, 3.4]]}}]'
    }, False)
    self.assertEqual(fields['folder'].key().id(), folder_id)
    del fields['folder']
    self.assertEqual(fields, {
        'name': 'abc',
        'view_location': db.GeoPt(4.5, 5.6),
        'view_is_camera': None
    })
    self.assertEqual(geometries, [
        {'type': model.LineString, 'fields': {
            'points': [db.GeoPt(1.2, 3.4)],
            'altitudes': [],
            'altitude_mode': None,
            'extrude': False,
            'tessellate': False
        }}
    ])

    # Success, no-op.
    fields, geometries = entity._ValidateEntityArguments(layer, {}, True)
    self.assertEqual(fields, {})
    self.assertEqual(geometries, [])

    # Failure, empty name.
    self.assertRaises(util.BadRequest, entity._ValidateEntityArguments, layer, {
        'name': '',
        'geometries': '[{"type":"Point","fields":{"location":[1.23,4.56]}}]'
    }, False)

    # Failure, no geometries.
    self.assertRaises(util.BadRequest, entity._ValidateEntityArguments, layer, {
        'name': 'abc',
        'geometries': '[]'
    }, False)

    # Invalid value.
    self.assertRaises(util.BadRequest, entity._ValidateEntityArguments, layer, {
        'name': 'abc',
        'view_range': 'xyz',
        'geometries': '[{"type":"Point","fields":{"location":[1.23,4.56]}}]'
    }, False)

    # Invalid JSON.
    self.assertRaises(util.BadRequest, entity._ValidateEntityArguments, layer, {
        'name': 'abc',
        'view_range': 'xyz',
        'geometries': '[{"type":"Point",fields":{"location":[1.23,4.56]}}]'
    }, False)
