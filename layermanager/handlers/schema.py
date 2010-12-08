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

"""The schemas editing page of the KML Layer Manager."""

from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors
import handlers.base
import model
import util


class SchemaHandler(handlers.base.PageHandler):
  """A form to create, update and delete schemas."""

  PERMISSION_REQUIRED = model.Permission.SCHEMAS
  FORM_TEMPLATE = 'schema'
  ASSOCIATED_MODEL = model.Schema

  def ShowForm(self, _):
    """Shows a schema editing form."""
    return {'field_model': model.Field}

  def ShowRaw(self, layer):
    """Writes out a JSON representation of the schema."""
    schema = util.GetInstance(model.Schema, self.request.get('id'))
    field_set = [i.key().id() for i in schema.field_set]
    template_set = [i.key().id() for i in schema.template_set]
    handlers.base.PageHandler.ShowRaw(self, layer, field_set=field_set,
                                      template_set=template_set)

  def Create(self, layer):
    """Creates a new schema.

    POST Args:
      name: The name of the new schema.

    Args:
      layer: The layer to which the new schema will belong.
    """
    try:
      schema = model.Schema(layer=layer, name=self.request.get('name', None))
      schema.put()
    except db.BadValueError, e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(schema.key().id())

  def Update(self, layer):
    """Updates a schema's name.

    POST Args:
      schema_id: The ID of the schema to update.
      name: The new name of the schema.

    Args:
      layer: The layer to which the schema to update belongs.
    """
    schema_id = self.request.get('schema_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    name = self.request.get('name', None)
    if name is not None:
      try:
        schema.name = name
        schema.put()
      except db.BadValueError, e:
        raise util.BadRequest(str(e))

  def Delete(self, layer):
    """Deletes a schema.

    If any entity references a template in this schema, an error is returned.

    POST Args:
      schema_id: The ID of the schema to delete.

    Args:
      layer: The layer to which the schema to delete belongs.
    """
    schema_id = self.request.get('schema_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)

    for template in schema.template_set:
      if template.entity_set.get():
        raise util.BadRequest('Entities reference a template from this schema.')

    schema.SafeDelete()


class TemplateHandler(handlers.base.PageHandler):
  """A form to create, update and delete templates."""

  PERMISSION_REQUIRED = model.Permission.SCHEMAS
  ASSOCIATED_MODEL = model.Template

  def ShowList(self, layer):
    """Handler to show a list of templates for a schema.

    GET Args:
      schema_id: The ID of the schema whose templates are to be listed.

    Args:
      layer: The layer to which the schema containing this template belongs.
    """
    schema_id = self.request.get('schema_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    query = model.Template.all(keys_only=True).filter('schema', schema)
    self.response.out.write(json.dumps([i.id() for i in query]))

  def ShowRaw(self, layer):
    """Writes out a JSON representation of the template.

    GET Args:
      schema_id: The ID of the schema to which the specified template belongs.

    Args:
      layer: The layer to which the schema containing this template belongs.
    """
    try:
      template_id = self.GetArgument('id', int)
      schema_id = self.GetArgument('schema_id', int)
    except ValueError:
      raise util.BadRequest('Invalid template or schema ID specified.')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    template = model.Template.get_by_id(template_id, parent=schema)
    if not template:
      raise util.BadRequest('Invalid template ID specified.')
    description = {'name': template.name, 'text': template.text}
    self.response.out.write(json.dumps(description))

  def Create(self, layer):
    """Creates a new template.

    POST Args:
      schema_id: The ID of the schema which the new template uses.
      name: The name of the template.
      text: The text of the template.

    Args:
      layer: The layer that contains the schema of the new template.
    """
    schema_id = self.request.get('schema_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    try:
      template = model.Template(schema=schema, parent=schema,
                                name=self.request.get('name', ''),
                                text=self.request.get('text', ''))
      template.put()
    except db.BadValueError, e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(template.key().id())

  def Update(self, layer):
    """Updates a template's name or text.

    POST Args:
      schema_id: The ID of the schema to which the specified template belongs.
      template_id: The ID of the template to update.
      name: The new name of the template.
      text: The new text of the template.

    Args:
      layer: The layer to which the schema of the template to update belongs.
    """
    schema_id = self.request.get('schema_id')
    template_id = self.request.get('template_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    try:
      template = model.Template.get_by_id(int(template_id), parent=schema)
      if not template: raise ValueError()
    except (TypeError, ValueError, db.BadKeyError):
      raise util.BadRequest('Invalid template specified.')

    try:
      template.name = self.request.get('name', template.name)
      template.text = self.request.get('text', template.text) or None
      template.ClearCache()
      template.put()
    except db.BadValueError, e:
      raise util.BadRequest(str(e))

  def Delete(self, layer):
    """Deletes a template.

    If any entity references this template, an error is returned.

    POST Args:
      schema_id: The ID of the schema to which the specified template belongs.
      template_id: The ID of the template to delete.

    Args:
      layer: The layer to which the schema of the template to delete belongs.
    """
    schema_id = self.request.get('schema_id')
    template_id = self.request.get('template_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    try:
      template = model.Template.get_by_id(int(template_id), parent=schema)
      if not template: raise ValueError()
    except (TypeError, ValueError, db.BadKeyError):
      raise util.BadRequest('Invalid template specified.')
    if template.entity_set.get():
      raise util.BadRequest('Entities reference this template.')
    template.delete()


class FieldHandler(handlers.base.PageHandler):
  """A form to create, update and delete fields."""

  PERMISSION_REQUIRED = model.Permission.SCHEMAS
  ASSOCIATED_MODEL = model.Field

  def ShowList(self, layer):
    """Handler to show a list of fields for a schema.

    GET Args:
      schema_id: The ID of the schema whose fields are to be listed.

    Args:
      layer: The layer to which the schema containing this field belongs.
    """
    schema_id = self.request.get('schema_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    query = model.Field.all(keys_only=True).filter('schema', schema)
    self.response.out.write(json.dumps([i.id() for i in query]))

  def ShowRaw(self, layer):
    """Writes out a JSON representation of the field.

    GET Args:
      schema_id: The ID of the schema to which the specified field belongs.

    Args:
      layer: The layer to which the schema containing this field belongs.
    """
    try:
      field_id = self.GetArgument('id', int)
      schema_id = self.GetArgument('schema_id', int)
    except ValueError:
      raise util.BadRequest('Invalid field or schema ID specified.')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    field = model.Field.get_by_id(field_id, parent=schema)
    if not field:
      raise util.BadRequest('Invalid field ID specified.')
    description = {'name': field.name, 'type': field.type, 'tip': field.tip}
    self.response.out.write(json.dumps(description))

  def Create(self, layer):
    """Creates a new field.

    POST Args:
      schema_id: The ID of the schema to which the new field belongs.
      name: The name of the field.
      tip: A brief description of the field.
      type: The type of the field (one of model.Field.TYPES).

    Args:
      layer: The layer that contains the schema of the new field.
    """
    schema_id = self.request.get('schema_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)

    try:
      name = self.request.get('name', None)
      if schema.field_set.filter('name', name).get():
        raise util.BadRequest('Field names must be unique per schema.')

      field = model.Field(schema=schema, parent=schema, name=name,
                          tip=self.request.get('tip', None),
                          type=self.request.get('type', None))
      field.put()
    except db.BadValueError, e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(field.key().id())

  def Delete(self, layer):
    """Deletes a field.

    Entities with dynamic properties for this field will have these properties
    removed.

    POST Args:
      field_id: The ID of the field to delete.
      schema_id: The ID of the schema to which the specified field belongs.

    Args:
      layer: The layer to which the schema of the field to delete belongs.
    """
    schema_id = self.request.get('schema_id')
    field_id = self.request.get('field_id')
    schema = util.GetInstance(model.Schema, schema_id, layer)
    try:
      field = model.Field.get_by_id(int(field_id), parent=schema)
      if not field: raise ValueError()
    except (TypeError, ValueError, db.BadKeyError):
      raise util.BadRequest('Invalid field specified.')
    field_name = field.name

    field.delete()

    _DeleteFieldReferences(layer, schema_id, field_name)


class FieldQueueHandler(handlers.base.PageHandler):
  """A handler to continue layer deletion after timing out."""

  PERMISSION_REQUIRED = None

  def Delete(self, layer):
    """Deletes the specified field and clears values for it from entities."""
    _DeleteFieldReferences(
        layer, self.request.get('schema_id'), self.request.get('field_name'))


def _DeleteFieldReferences(layer, schema_id, field_name):
  """Deletes the specified field and clears values for it from entities."""
  try:
    schema = util.GetInstance(model.Schema, schema_id, layer)
    templates = list(schema.template_set)
    field_property = 'field_' + field_name
    for template in templates:
      for entity in template.entity_set:
        if hasattr(entity, field_property):
          delattr(entity, field_property)
          entity.put()
  except (runtime.DeadlineExceededError, db.Error,
          apiproxy_errors.OverQuotaError):
    # Schedule continuation.
    taskqueue.add(url='/field-continue-delete/%d' % layer.key().id(),
                  params={'schema_id': schema_id, 'field_name': field_name})
