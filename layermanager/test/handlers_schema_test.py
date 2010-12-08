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

"""Medium tests for the Schema, Template and Field handlers."""


import StringIO
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from handlers import base
from handlers import schema
from lib.mox import mox
import model
import util


class SchemaHandlerTest(mox.MoxTestBase):

  def testShowRaw(self):
    self.mox.StubOutWithMock(base.PageHandler, 'ShowRaw')
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_to_show = model.Schema(layer=layer, name='abc')
    schema_id = schema_to_show.put().id()
    field1_id = model.Field(
        schema=schema_to_show, name='a', type='image').put().id()
    field2_id = model.Field(
        schema=schema_to_show, name='b', type='icon').put().id()
    template1_id = model.Template(
        schema=schema_to_show, name='c', text='d').put().id()
    template2_id = model.Template(
        schema=schema_to_show, name='e', text='f').put().id()
    handler = schema.SchemaHandler()
    handler.request = {'id': schema_id}

    base.PageHandler.ShowRaw(handler, layer,
                             field_set=[field1_id, field2_id],
                             template_set=[template1_id, template2_id])

    self.mox.ReplayAll()
    handler.ShowRaw(layer)

  def testDeleteSuccess(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = schema.SchemaHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_schema = self.mox.CreateMock(model.Schema)
    mock_schema.template_set = []
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('schema_id').AndReturn(dummy_id)
    util.GetInstance(model.Schema, dummy_id, dummy_layer).AndReturn(mock_schema)
    mock_schema.SafeDelete()

    self.mox.ReplayAll()
    handler.Delete(dummy_layer)

  def testDeleteSimpleFailure(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = schema.SchemaHandler()
    handler.request = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('schema_id').AndReturn(dummy_id)
    util.GetInstance(model.Schema, dummy_id, dummy_layer).AndRaise(
        util.BadRequest)

    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)

  def testDeleteReferenceFailure(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = schema.SchemaHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_schema = self.mox.CreateMock(model.Schema)
    mock_template = self.mox.CreateMock(model.Template)
    mock_template.entity_set = self.mox.CreateMockAnything()
    mock_schema.template_set = [mock_template]
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('schema_id').AndReturn(dummy_id)
    util.GetInstance(model.Schema, dummy_id, dummy_layer).AndReturn(mock_schema)
    mock_template.entity_set.get().AndReturn(object())

    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)

  def testCreateSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    handler = schema.SchemaHandler()
    handler.request = {'name': 'abc'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Schema.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'abc')

  def testCreateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    handler = schema.SchemaHandler()

    # No name.
    handler.request = {'name': ''}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Name too long.
    handler.request = {'name': 'a' * 700}
    self.assertRaises(util.BadRequest, handler.Create, layer)

  def testUpdateSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_id = model.Schema(layer=layer, name='abc').put().id()

    handler = schema.SchemaHandler()

    # No-op.
    handler.request = {'schema_id': str(schema_id)}
    handler.Update(layer)
    updated_schema = model.Schema.get_by_id(schema_id)
    self.assertEqual(updated_schema.name, 'abc')

    # Name change.
    handler.request = {'schema_id': str(schema_id), 'name': 'def'}
    handler.Update(layer)
    updated_schema = model.Schema.get_by_id(schema_id)
    self.assertEqual(updated_schema.name, 'def')

  def testUpdateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_id = model.Schema(layer=layer, name='abc').put().id()

    handler = schema.SchemaHandler()

    # No schema ID.
    handler.request = {'name': 'abc'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Empty name.
    handler.request = {'schema_id': str(schema_id), 'name': ''}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Overly long name.
    handler.request = {'schema_id': str(schema_id), 'name': 'a' * 700}
    self.assertRaises(util.BadRequest, handler.Update, layer)


class TemplateHandlerTest(mox.MoxTestBase):

  def testShowList(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema1 = model.Schema(layer=layer, name='abc')
    schema1_id = schema1.put().id()
    schema2 = model.Schema(layer=layer, name='def')
    schema2.put()
    template1_id = model.Template(schema=schema1, name='a', text='b').put().id()
    model.Template(schema=schema2, name='c', text='d')
    template3_id = model.Template(schema=schema1, name='e', text='f').put().id()
    handler = schema.TemplateHandler()
    handler.request = {'schema_id': schema1_id}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()

    handler.response.out.write('[%d, %d]' % (template1_id, template3_id))

    self.mox.ReplayAll()
    handler.ShowList(layer)

  def testDeleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='abc')
    schema_id = schema_object.put().id()
    template_id = model.Template(schema=schema_object, parent=schema_object,
                                 name='b', text='c').put().id()

    handler = schema.TemplateHandler()
    handler.request = {'schema_id': str(schema_id),
                       'template_id': str(template_id)}
    self.assertTrue(model.Template.get_by_id(template_id, parent=schema_object))
    handler.Delete(layer)
    self.assertFalse(model.Template.get_by_id(template_id,
                                              parent=schema_object))

  def testDeleteFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()
    template = model.Template(schema=schema_object, parent=schema_object,
                              name='c', text='d')
    template_id = template.put().id()

    # No schema ID.
    handler = schema.TemplateHandler()
    handler.request = {'template_id': str(template_id)}
    self.assertRaises(util.BadRequest, handler.Delete, layer)

    # A referencing entity exists.
    model.Entity(layer=layer, name='e', template=template).put()
    handler = schema.TemplateHandler()
    handler.request = {'schema_id': str(schema_id),
                       'template_id': str(template_id)}
    self.assertRaises(util.BadRequest, handler.Delete, layer)

  def testCreateSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()

    handler = schema.TemplateHandler()
    handler.request = {'schema_id': str(schema_id), 'name': 'abc', 'text': 'de'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Template.get_by_id(int(handler.response.out.getvalue()),
                                      parent=schema_object)
    self.assertEqual(result.schema.key().id(), schema_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.text, 'de')

  def testCreateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()
    handler = schema.TemplateHandler()

    # No schema ID.
    handler.request = {'name': 'a', 'text': 'b'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Non-existent schema ID.
    handler.request = {'schema_id': str(schema_id + 1),
                       'name': 'a', 'text': 'b'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Empty name.
    handler.request = {'schema_id': str(schema_id), 'name': '', 'text': 'b'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Overly long name.
    handler.request = {'schema_id': str(schema_id), 'name': 'a' * 700}
    self.assertRaises(util.BadRequest, handler.Create, layer)

  def testUpdateSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()
    template = model.Template(schema=schema_object, parent=schema_object,
                              name='abc', text='def')
    template_id = template.put().id()
    handler = schema.TemplateHandler()

    # No-op.
    handler.request = {'schema_id': str(schema_id),
                       'template_id': str(template_id)}
    handler.Update(layer)
    result = model.Template.get_by_id(template_id, parent=schema_object)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.text, 'def')

    # Actual update.
    handler.request = {'schema_id': str(schema_id),
                       'template_id': str(template_id),
                       'name': 'hello', 'text': 'world'}
    handler.Update(layer)
    result = model.Template.get_by_id(template_id, parent=schema_object)
    self.assertEqual(result.name, 'hello')
    self.assertEqual(result.text, 'world')

  def testUpdateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()
    template = model.Template(schema=schema_object, parent=schema_object,
                              name='abc', text='def')
    template_id = template.put().id()

    handler = schema.TemplateHandler()

    handler.request = {}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # No template ID.
    handler.request = {'schema_id': str(schema_id)}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # No schema ID.
    handler.request = {'template_id': str(template_id)}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Empty name.
    handler.request = {'schema_id': str(schema_id),
                       'template_id': str(template_id),
                       'name': ''}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Overly long name.
    handler.request = {'schema_id': str(schema_id),
                       'template_id': str(template_id),
                       'name': 'a' * 700}
    self.assertRaises(util.BadRequest, handler.Update, layer)


class FieldHandlerTest(mox.MoxTestBase):

  def testShowList(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema1 = model.Schema(layer=layer, name='abc')
    schema1_id = schema1.put().id()
    schema2 = model.Schema(layer=layer, name='def')
    schema2.put()
    field1_id = model.Field(
        schema=schema1, name='a', type='image').put().id()
    model.Field(
        schema=schema2, name='c', type='icon').put()
    field3_id = model.Field(
        schema=schema1, name='e', type='resource').put().id()
    handler = schema.FieldHandler()
    handler.request = {'schema_id': schema1_id}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = self.mox.CreateMockAnything()

    handler.response.out.write('[%d, %d]' % (field1_id, field3_id))

    self.mox.ReplayAll()
    handler.ShowList(layer)

  def testDeleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='abc')
    schema_id = schema_object.put().id()
    field_id = model.Field(schema=schema_object, parent=schema_object,
                           name='b', type='string').put().id()
    template = model.Template(schema=schema_object, parent=schema_object,
                              name='c', text='d')
    template.put()
    entity = model.Entity(layer=layer, name='x', field_b='hello',
                          template=template)
    entity_id = entity.put().id()

    handler = schema.FieldHandler()
    handler.request = {'schema_id': str(schema_id), 'field_id': str(field_id)}
    self.assertTrue(model.Field.get_by_id(field_id, parent=schema_object))
    self.assertTrue(hasattr(model.Entity.get_by_id(entity_id), 'field_b'))
    handler.Delete(layer)
    self.assertFalse(model.Field.get_by_id(field_id, parent=schema_object))
    self.assertFalse(hasattr(model.Entity.get_by_id(entity_id), 'field_b'))

  def testDeleteFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()
    field_id = model.Field(schema=schema_object, parent=schema_object,
                           name='b', type='string').put().id()

    # No field ID.
    handler = schema.FieldHandler()
    handler.request = {'schema_id': str(schema_id)}
    self.assertRaises(util.BadRequest, handler.Delete, layer)

    # No schema ID.
    handler = schema.FieldHandler()
    handler.request = {'field_id': str(field_id)}
    self.assertRaises(util.BadRequest, handler.Delete, layer)

    # Non-existent schema ID.
    handler = schema.FieldHandler()
    handler.request = {'schema_id': str(schema_id + 1),
                       'field_id': str(field_id)}
    self.assertRaises(util.BadRequest, handler.Delete, layer)

  def testDeleteInterrupt(self):
    self.mox.StubOutWithMock(taskqueue, 'add')
    self.mox.StubOutWithMock(util, 'GetInstance')
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_key = self.mox.CreateMockAnything()
    dummy_id = object()
    dummy_name = object()

    util.GetInstance(model.Schema, dummy_id, mock_layer).AndRaise(db.Error)
    mock_layer.key().AndReturn(mock_key)
    mock_key.id().AndReturn(42)
    taskqueue.add(url='/field-continue-delete/42',
                  params={'schema_id': dummy_id, 'field_name': dummy_name})

    self.mox.ReplayAll()
    schema._DeleteFieldReferences(mock_layer, dummy_id, dummy_name)

  def testCreateSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()

    handler = schema.FieldHandler()
    handler.request = {'schema_id': str(schema_id),
                       'name': 'abc', 'type': 'date', 'tip': 'def'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Field.get_by_id(int(handler.response.out.getvalue()),
                                   parent=schema_object)
    self.assertEqual(result.schema.key().id(), schema_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.type, 'date')
    self.assertEqual(result.tip, 'def')

  def testCreateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema_object = model.Schema(layer=layer, name='b')
    schema_id = schema_object.put().id()
    model.Field(schema=schema_object, parent=schema_object,
                name='existing', type='string').put()
    handler = schema.FieldHandler()

    # No schema ID.
    handler.request = {'name': 'a', 'type': 'date'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid schema ID.
    handler.request = {'schema_id': str(schema_id + 1),
                       'name': 'a', 'type': 'date'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Empty name.
    handler.request = {'schema_id': str(schema_id),
                       'name': '', 'type': 'date'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Overly long name.
    handler.request = {'schema_id': str(schema_id),
                       'name': 'a' * 700, 'type': 'date'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Overly long tip.
    handler.request = {'schema_id': str(schema_id),
                       'name': 'a', 'type': 'date', 'tip': 'a' * 700}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid type.
    handler.request = {'schema_id': str(schema_id),
                       'name': 'a', 'type': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Duplicate name.
    handler.request = {'schema_id': str(schema_id),
                       'name': 'existing', 'type': 'date'}
    self.assertRaises(util.BadRequest, handler.Create, layer)
