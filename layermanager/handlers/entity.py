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

"""The entity editing page of the KML Layer Manager."""

import copy
import datetime
from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.ext import db
import handlers.base
import model
import util


class EntityHandler(handlers.base.PageHandler):
  """A form to query, create, update and delete entities."""

  PERMISSION_REQUIRED = model.Permission.ENTITIES
  FORM_TEMPLATE = 'entity'
  ASSOCIATED_MODEL = model.Entity

  def ShowForm(self, layer):
    """Shows an entity editing form."""
    if layer.auto_managed:
      return {}
    else:
      entities = []
      for entity in layer.entity_set:
        entity.custom_fields = entity.dynamic_properties() or None
        geometry_objects = []
        for geometry in _GetGeometriesDescription(entity):
          fields = copy.copy(geometry)
          del fields['type']
          geometry_objects.append({
              'type': geometry['type'],
              'fields': json.dumps(fields)
          })
        entity.geometry_objects = geometry_objects or None
        entities.append(entity)
      return {'entities': entities}

  def ShowRaw(self, layer):
    """Writes out a JSON representation of the entity."""
    entity = util.GetInstance(model.Entity, self.request.get('id'), layer)
    extras = {}

    for field_name in entity.dynamic_properties():
      value = getattr(entity, field_name)
      if isinstance(value, datetime.datetime):
        value = value.strftime('%Y-%m-%d %H:%M:%S')
      extras[field_name] = value

    extras['geometries'] = _GetGeometriesDescription(entity)

    handlers.base.PageHandler.ShowRaw(self, layer, **extras)

  def Create(self, layer):
    """Creates a new entity and writes out its ID.

    POST Args:
      name: The name of the new entity.
      snippet: A brief description of the entity. Optional.
      view_latitude: The latitude of the spot at which the camera showing this
          entity should point. Optional.
      view_longitude: The longitude of the spot at which the camera showing this
          entity should point. Optional.
      view_altitude: The altitude of the spot at which the camera showing this
          entity should point. Optional.
      view_heading: The rotation of the camera around the axis perpendicular to
          the planet surface in degrees (0 is North). Optional.
      view_tilt: The angle between the direction of the camara and the normal to
          the planet surface, in degrees (0 is straight down). Optional.
      view_range: The distance in meters from the point specified by latitude,
          longitude and altitude to the camera. Optional.
      region: The ID of the region to which this entity belongs. Optional.
      priority: This entity's priority. Used during auto-regionation for
          selecting entities to display in larger regions. Optional. Ignored for
          non-auto-managed layers.
      folder: The ID of the folder in which this entity should be created.
          Optional.
      folder_index: The index of the entity in its parent folder. Entities with
          higher indices come after entities with lower indices within a single
          folder. Optional.
      style: The ID of the style that applies to this entity. Optional.
      schema: The ID of the schema that this entity uses. Optional.
      template: The ID of the template for this entity's bubble. Optional.
          If specified, schema must also be specified.
      field_*: A value for a schema field (e.g. field_foo for the field called
          "foo". The field names must be from the schema to which this entity's
          template belongs and must be of a type compatible with the field's
          type (consult model.Field for details). These will be stored as
          dynamic properties of the Entity.
      geometries: A JSON array of geometries. Each geometry has two properties:
          type: The type of the geometry which is rendered for this entity.
            This must be the name of one of the leaf model.Geometry subclasses.
          fields: An object mapping field names defined by the selected geometry
            to values. For the type of fields each type of geometry expects,
            consult model.py. GeoPt properties are represented as a 2-element
            [lat, lon] array. Resources are represented by their IDs.

    Args:
      layer: The layer to which the new entity will belong.
    """
    post_arguments = dict((argument, self.request.get(argument))
                          for argument in self.request.arguments())
    fields, geometries = _ValidateEntityArguments(layer, post_arguments, False)
    try:
      layer.ClearCache()
      entity_id = db.run_in_transaction(_CreateEntityAndGeometry,
                                        layer, fields, geometries)
      model.Entity.get_by_id(entity_id).GenerateKML()  # Build cache.
    except db.BadValueError, e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(entity_id)

  def BulkCreate(self, layer):
    """Creates a number of new entities in bulk.

    Writes out one or more lines of output. The first is a comma-separated list
    of IDs of entities created successfully. The rest are an error message if an
    error was encountered. If no errors were encountered, an empty second line
    is written. Entities are created sequentially, so the number of IDs on the
    first line of output is enough to pinpoint the problematic entity.

    POST Args:
      entities: A JSON array of entity specifications, each specification
          containing properties similar to the POST parameters to Create().

    Args:
      layer: The layer to which the new entities will belong.
    """
    try:
      entities = json.loads(self.request.get('entities'))
    except:
      raise util.BadRequest('Invalid JSON syntax in entities specification.')

    created_entity_ids = []
    error = ''
    try:
      layer.ClearCache()
      for entity in entities:
        try:
          fields, geometries = _ValidateEntityArguments(layer, entity, False)
          entity_id = db.run_in_transaction(_CreateEntityAndGeometry,
                                            layer, fields, geometries)
          created_entity_ids.append(entity_id)
        except (db.BadValueError, TypeError, ValueError, util.BadRequest), e:
          error = str(e)
          break
    except runtime.DeadlineExceededError:
      # We still want to write out the entity IDs.
      error = 'Ran out of time.'

    self.response.out.write(','.join(str(i) for i in created_entity_ids))
    self.response.out.write('\n')
    self.response.out.write(error)

  def Update(self, layer):
    """Update an entity's properties.

    POST Args:
      entity_id: The ID of the entity to update.
      Also accepts all the same arguments as Create() above. Note that if any
      geometries are specified, they overwrite all old geometries.

    Args:
      layer: The layer to which the entity to update belongs.
    """
    entity_id = self.request.get('entity_id')
    entity = util.GetInstance(model.Entity, entity_id, layer)

    post_arguments = dict((argument, self.request.get(argument))
                          for argument in self.request.arguments())
    fields, geometries = _ValidateEntityArguments(layer, post_arguments, True)

    clear_fields = (fields.get('template') is None or
                    (fields.get('template') and entity.template and
                     fields['template'].schema.key() !=
                     entity.template.schema.key()))
    try:
      entity.ClearCache()
      db.run_in_transaction(_UpdateEntityAndGeometry,
                            int(entity_id), fields, geometries, clear_fields)
      model.Entity.get_by_id(int(entity_id)).GenerateKML()  # Rebuild cache.
    except db.BadValueError, e:
      raise util.BadRequest(str(e))

  def Delete(self, layer):
    """Deletes the entity.

    POST Args:
      entity_id: The ID of the entity to delete.

    Args:
      layer: The layer to which the entity to delete belongs.
    """
    entity_id = self.request.get('entity_id')
    entity = util.GetInstance(model.Entity, entity_id, layer)
    layer.ClearCache()
    entity.SafeDelete()


def _CreateEntityAndGeometry(layer, fields, geometries):
  """Creates an entity and its geometry in a single group.

  Args:
    layer: The layer that will contain the new entity.
    fields: The properties of the new entity.
    geometries: Specifications of the geometries of the new entity, in the same
        format as returned by _ValidateEntityArguments().

  Returns:
    The ID of the new entity.
  """
  entity = model.Entity(layer=layer, **fields)
  entity.put()
  geometry_objects = []
  for geometry in geometries:
    geometry_object = geometry['type'](parent=entity, **geometry['fields'])
    geometry_object.put()
    geometry_objects.append(geometry_object)
    entity.geometries.append(geometry_object.key().id())
  entity.UpdateLocation(geometry_objects[0])
  entity.put()
  return entity.key().id()


def _UpdateEntityAndGeometry(entity_id, fields, geometries, clear_fields):
  """Updates the entity and swaps geometries if new ones are specifeid.

  Args:
    entity_id: The ID of the entity to edit.
    fields: The fields to set on the entity.
    geometries: Specifications of the geometries of the new entity, in the same
        format as returned by _ValidateEntityArguments(). If this evaluates to
        False in boolean context, the old geometries are left untouched.
    clear_fields: Whether to delete old synamic properties.

  Returns:
    The ID of the new entity.
  """
  entity = model.Entity.get_by_id(entity_id)

  if clear_fields:
    for dynamic_property in entity.dynamic_properties():
      delattr(entity, dynamic_property)
  for field, value in fields.iteritems():
    setattr(entity, field, value)

  if geometries is not None:
    for old_geometry in entity.geometries:
      old_geometry = model.Geometry.get_by_id(old_geometry, parent=entity)
      old_geometry.delete()
    entity.geometries = []
    geometry_objects = []
    for geometry in geometries:
      geometry_object = geometry['type'](parent=entity, **geometry['fields'])
      geometry_object.put()
      geometry_objects.append(geometry_object)
      entity.geometries.append(geometry_object.key().id())
  entity.UpdateLocation(geometry_objects[0])
  entity.put()


def _PrepareGeometryFields(geometry_type, fields, layer):
  """Cleans and typecasts fields of the entity's Geometry object.

  Args:
    geometry_type: A string indicating the type of geometry. Must be the name of
        one of the leaf subclasses of model.Geometry.
    fields: A dictionary of raw fields describing the geometry.
    layer: The layer to which the entity that will contain this gometry belongs.

  Returns:
    A dictionary of parameters ready to pass to the constructor of one of the
    leaf subclasses of Geometry.

  Raises:
    TypeError: If an unknown geometry type is supplied.
  """

  def GetResource(resource_id, types):
    """Gets a Resource from the datastore by its ID and validates its type."""
    if isinstance(types, basestring): types = (types,)
    resource = util.GetInstance(model.Resource, resource_id, layer)
    if resource.type not in types:
      message = 'Resource of invalid type specified. Must be one of %s.' % types
      raise util.BadRequest(message)
    return resource

  if geometry_type == 'Point':
    altitude = fields.get('altitude') or None
    if altitude is not None: altitude = float(altitude)
    return {'location': db.GeoPt(*fields.get('location') or []),
            'altitude': altitude,
            'altitude_mode': fields.get('altitude_mode') or None,
            'extrude': bool(fields.get('extrude'))}
  elif geometry_type == 'LineString':
    points = [db.GeoPt(*i) for i in fields.get('points') or []]
    altitudes = [float(i) for i in fields.get('altitudes') or []]
    return {'points': points,
            'altitudes': altitudes,
            'altitude_mode': fields.get('altitude_mode') or None,
            'extrude': bool(fields.get('extrude')),
            'tessellate': bool(fields.get('tessellate'))}
  elif geometry_type == 'Polygon':
    outer_points = [db.GeoPt(*i) for i in fields.get('outer_points') or []]
    outer_altitudes = [float(i) for i in fields.get('outer_altitudes') or []]
    inner_points = [db.GeoPt(*i) for i in fields.get('inner_points') or []]
    inner_altitudes = [float(i) for i in fields.get('inner_altitudes') or []]
    return {'outer_points': outer_points,
            'outer_altitudes': outer_altitudes,
            'inner_points': inner_points,
            'inner_altitudes': inner_altitudes,
            'altitude_mode': fields.get('altitude_mode') or None,
            'extrude': bool(fields.get('extrude')),
            'tessellate': bool(fields.get('tessellate'))}
  elif geometry_type == 'Model':
    for field_name, field_value in fields.items():
      if isinstance(field_value, int):
        fields[field_name] = float(field_value)
    alias_sources = fields.get('resource_alias_sources') or []
    alias_targets = []
    for alias in fields.get('resource_alias_targets') or []:
      alias_targets.append(GetResource(alias, 'image'))
    model_resource = GetResource(fields.get('model'), ('model', 'model_in_kmz'))
    return {'location': db.GeoPt(*fields.get('location') or []),
            'altitude': fields.get('altitude') or None,
            'altitude_mode': fields.get('altitude_mode') or None,
            'model': model_resource,
            'heading': fields.get('heading') or None,
            'tilt': fields.get('tilt') or None,
            'roll': fields.get('roll') or None,
            'scale_x': fields.get('scale_x') or None,
            'scale_y': fields.get('scale_y') or None,
            'scale_z': fields.get('scale_z') or None,
            'resource_alias_sources': alias_sources,
            'resource_alias_targets': alias_targets}
  elif geometry_type == 'GroundOverlay':
    for field_name, field_value in fields.items():
      if isinstance(field_value, int):
        fields[field_name] = float(field_value)
    altitude_mode = fields.get('altitude_mode')
    draw_order = fields.get('draw_order', None)
    if draw_order is not None: draw_order = int(draw_order)
    is_quad = fields.get('is_quad', None) is not None
    overlay = {'image': GetResource(fields.get('image'), 'image'),
               'color': fields.get('color') or None,
               'draw_order': draw_order,
               'altitude': fields.get('altitude') or None,
               'altitude_mode': altitude_mode or None,
               'is_quad': is_quad}
    if is_quad:
      overlay.update({
          'corners': [db.GeoPt(*i) for i in fields.get('corners') or []],
      })
    else:
      overlay.update({
          'north': fields.get('north'),
          'south': fields.get('south'),
          'west': fields.get('west'),
          'east': fields.get('east'),
          'rotation': fields.get('rotation') or None
      })
    return overlay
  elif geometry_type == 'PhotoOverlay':
    for field_name, field_value in fields.items():
      if isinstance(field_value, int):
        fields[field_name] = float(field_value)
    location = db.GeoPt(*fields.get('location') or [])
    draw_order = fields.get('draw_order', None)
    if draw_order is not None: draw_order = int(draw_order)
    pyramid_tile_size = fields.get('pyramid_tile_size', None)
    if pyramid_tile_size is not None: pyramid_tile_size = int(pyramid_tile_size)
    pyramid_height = fields.get('pyramid_height', None)
    if pyramid_height is not None: pyramid_height = int(pyramid_height)
    pyramid_width = fields.get('pyramid_width', None)
    if pyramid_width is not None: pyramid_width = int(pyramid_width)

    return {'image': GetResource(fields.get('image'), 'image'),
            'color': fields.get('color') or None,
            'draw_order': draw_order,
            'view_left': fields.get('view_left'),
            'view_right': fields.get('view_right'),
            'view_top': fields.get('view_top'),
            'view_bottom': fields.get('view_bottom'),
            'view_near': fields.get('view_near'),
            'shape': fields.get('shape'),
            'location': location,
            'altitude': fields.get('altitude') or None,
            'rotation': fields.get('rotation') or None,
            'pyramid_tile_size': pyramid_tile_size,
            'pyramid_height': pyramid_height,
            'pyramid_width': pyramid_width,
            'pyramid_grid_origin': fields.get('pyramid_grid_origin') or None}
  else:
    raise TypeError('Unknown geometry type specified: %s' % geometry_type)


def _ValidateEntityArguments(layer, post_arguments, allow_missing_args):
  """Validates post arguments used to create or edit an entity.

  Args:
    layer: The layer to which the entity to create or update belongs.
    post_arguments: A dictionary mapping POST arguments to their values. The
        exact arguments used are described in EntityHandler.Create().
    allow_missing_args: A boolean specifying whether required argument are
        allowed to be missing (used when updating only some properties).

  Returns:
    A 2-tuple. The first element is a dictionary mapping all valid entity
    argument names to their cleaned up values, converted to their proper type
    ready for storage. The second is a dictionary containing a geometry type and
    arguments to its constructor or None if no geometries were specified.

  Raises:
    util.BadRequest: if any field fails validation.
  """
  # TODO: Refactor.
  clean_fields = {}

  for argument in post_arguments.keys():  # pylint: disable-msg=C6401
    if post_arguments[argument] is None:
      del post_arguments[argument]
    elif post_arguments[argument] == '':  # pylint: disable-msg=C6403
      post_arguments[argument] = None

  if (post_arguments.get('view_latitude') and
      post_arguments.get('view_longitude')):
    post_arguments['view_location'] = [post_arguments['view_latitude'],
                                       post_arguments['view_longitude']]
    del post_arguments['view_latitude']
    del post_arguments['view_longitude']

  # Simple number/string/point properties.
  for field, required in (('name', not allow_missing_args),
                          ('snippet', False),
                          ('folder_index', False),
                          ('view_location', False),
                          ('view_altitude', False),
                          ('view_heading', False),
                          ('view_tilt', False),
                          ('view_range', False),
                          ('view_roll', False),
                          ('view_is_camera', False),
                          ('priority', False)):
    if field in post_arguments:
      property_object = getattr(model.Entity, field)
      try:
        value = post_arguments.get(field, None)
        if value is not None:
          if issubclass(property_object.data_type, basestring):
            value = unicode(value)
          elif property_object.data_type is db.GeoPt:
            value = db.GeoPt(*value)
          else:
            value = property_object.data_type(value)
        value = property_object.validate(value)
      except (TypeError, ValueError, db.BadValueError):
        raise util.BadRequest('Invalid %s specified: %s' % (field, value))
      clean_fields[field] = value
    elif required:
      raise util.BadRequest('%s, a required field, is missing.' % field.title())

  # Reference properties.
  for field in ('style', 'folder', 'region'):
    field_model = getattr(model, field.title())
    if field in post_arguments:
      value = post_arguments.get(field) or None
      if value:
        clean = util.GetInstance(field_model, value, layer)
        clean_fields[field] = clean
      else:
        clean_fields[field] = None
  if 'template' in post_arguments:
    schema_id = post_arguments.get('schema') or None
    template_id = post_arguments.get('template') or None
    if not schema_id and not template_id:
      clean_fields['schema'] = clean_fields['template'] = None
    else:
      schema = util.GetInstance(model.Schema, schema_id, layer)
      try:
        template = model.Template.get_by_id(int(template_id), parent=schema)
      except (ValueError, db.BadKeyError):
        raise util.BadRequest('Invalid template ID specified.')
      else:
        clean_fields['template'] = template

  # Schema fields.
  schema_fields = [(name[len('field_'):], value)
                   for name, value in post_arguments.iteritems()
                   if name.startswith('field_') and value is not None]

  if clean_fields.get('template'):
    template = clean_fields['template']
    unfilled_fields = dict((field.name, field)
                           for field in template.schema.field_set)
    for field_name, field_value in schema_fields:
      if field_name in unfilled_fields:
        if value == '':  # pylint: disable-msg=C6403
          clean_fields['field_' + field_name.encode('utf8')] = None
        else:
          field = unfilled_fields[field_name]
          cleaned_value = field.Validate(field_value)
          if cleaned_value is not None:
            clean_fields['field_' + field_name.encode('utf8')] = cleaned_value
            del unfilled_fields[field_name]
          else:
            raise util.BadRequest('Schema field "%s" is not a valid %s.' %
                                  (field_name, field.type))
      else:
        raise util.BadRequest('Field "%s" not in schema.' % field_name)

  # Geometries.
  geometries = post_arguments.get('geometries')
  cleaned_geometries = []
  if geometries:
    try:
      geometries = json.loads(post_arguments.get('geometries'))
    except ValueError:
      raise util.BadRequest('Invalid JSON syntax in geometries specification.')

    try:
      for geometry in geometries:
        geometry['fields'] = _PrepareGeometryFields(
            geometry['type'], geometry['fields'], layer)
        geometry['type'] = getattr(model, geometry['type'])
        cleaned_geometries.append(geometry)
    except (TypeError, IndexError, KeyError, ValueError, db.BadValueError), e:
      raise util.BadRequest('Invalid geometries specification: %s' % e)

  if not cleaned_geometries and not allow_missing_args:
    raise util.BadRequest('No geometries specified.')

  return clean_fields, cleaned_geometries


class EntityBalloonHandler(handlers.base.PageHandler):
  """A handler to dynamically serve entity balloons to the Earth client."""

  PERMISSION_REQUIRED = None

  def ShowRaw(self, layer):
    """Writes out the contents of an entity's balloon.

    GET Args:
      id: The ID of the entity whose balloon to get, prefixed with "id".
      link_template: A template for links between entities (e.g. flyTo links)
          with a placeholder string equal to settings.BALLOON_LINK_PLACEHOLDER.

    Args:
      layer: The layer to which the specified entity belongs.
    """
    entity_id = self.request.get('id', '')[2:]
    entity = util.GetInstance(model.Entity, entity_id, layer)
    if not layer.dynamic_balloons:
      raise util.BadRequest('Layer does not serve dynamic balloon content.')
    if not entity.template:
      raise util.BadRequest('Entity has no template to evaluate.')

    link_template = self.request.get('link_template')
    content = entity.template.Evaluate(
        entity, False, self._cache, link_template)

    self.response.out.write(content)


def _GetGeometriesDescription(entity):
  """Returns a JSON representation of an entity's geometries."""
  geometries = []

  def FormatGeometryField(value):
    if isinstance(value, db.GeoPt):
      return [value.lat, value.lon]
    elif isinstance(value, list):
      return [FormatGeometryField(i) for i in value]
    elif isinstance(value, db.Model):
      return value.key().id()
    else:
      return value

  for geometry in entity.geometries:
    result = {}
    geometry = model.Geometry.get_by_id(geometry, parent=entity)
    for name in geometry.properties():
      value = getattr(geometry, name)
      result[name] = FormatGeometryField(value)
    result['type'] = geometry.class_name()
    del result['_class']
    geometries.append(result)
  return geometries
