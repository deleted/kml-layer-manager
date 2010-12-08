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

"""Custom Django template tags and filters for entity templates."""


from google.appengine.ext.webapp import template
import model
import settings
import util


register = template.create_template_register()


class _ContextSuppliedTag(template.django.template.Node):
  """Runs a simple tag function with an implicit context argument."""

  def __init__(self, function, arguments):
    self.arguments = arguments
    self.function = function

  def render(self, context):  # pylint: disable-msg=C6409
    """Evaluates arguments and passes them to self.function()."""
    evaluated_arguments = []
    for argument in self.arguments:
      if argument.startswith('"') and argument[0] == argument[-1]:
        evaluated_arguments.append(argument[1:-1])
      else:
        value = template.django.template.resolve_variable(argument, context)
        evaluated_arguments.append(value)
    return self.function(context, *evaluated_arguments)

  @staticmethod
  def Parse(token, function):
    """Parses the tag code string."""
    max_arguments = function.func_code.co_argcount - 1  # Account for context.
    min_arguments = max_arguments - len(function.func_defaults or [])
    arguments = token.split_contents()[1:]
    if len(arguments) < min_arguments or len(arguments) > max_arguments:
      params = (min_arguments, max_arguments, token.contents.split()[0])
      message = 'From %d to %d arguments required for %s.' % params
      raise template.django.template.TemplateSyntaxError(message)
    return _ContextSuppliedTag(function, arguments)

  @staticmethod
  def Register(function):
    """Registers a function as a tag with an implicit context argument."""
    parser = lambda _, token: _ContextSuppliedTag.Parse(token, function)
    register.tag(function.__name__, parser)
    return function


def _GetEntitySiblings(entity, cache=None):
  """Gets a sorted list of all entities in the entity's folder.

  Args:
    entity: The entity whose siblings are to be computed.
    cache: An optional dictionary of caches to use and fill.

  Returns:
    A list of children of the entity's parent, including the entity.
  """
  if entity.folder:
    parent = entity.folder
  else:
    parent = entity.layer
  parent_id = parent.key().id()

  if cache is None:
    entity_cache = {}
  else:
    entity_cache = cache['entity_siblings']

  if parent_id not in entity_cache:
    contents = parent.entity_set
    if not entity.folder: contents = contents.filter('folder', None)
    contents = sorted(contents, key=lambda x: x.folder_index)
    entity_cache[parent_id] = [i.key().id() for i in contents if i.template]

  return entity_cache[parent_id]


def _GetFlyToLink(target_id, link_type, link_template=None):
  """Creates a ballonFlyto link, either ordinary or from a link template.

  Args:
    target_id: The ID of the target entity.
    link_type: The type of link to create, e.g. "balloon" or "flyTo".
    link_template: A template for inter-entity links sent back from a balloon
        bootstrap. All we know about it is that replacing the placeholder string
        with a valid alphanumeric ID will give us a valid entity link.

  Returns:
    A string that can be used in the HREF attribute of an HTML <a> link.
  """
  target = 'id%d' % target_id
  if link_template:
    link = link_template.replace(settings.BALLOON_LINK_PLACEHOLDER, target)
    return link.replace('balloonFlyto', link_type).encode('utf8')
  else:
    return (u'#%s;%s' % (target, link_type)).encode('utf8')


def _GetOffsetLink(context, entity, offset, link_type):
  """Returns a link to the entity at offset distance from the specified one.

  Trying to generate links in auto-managed layers will result in an error, as
  entities are scattered across several files, and even if we calculate the
  appropriate file, the next time the layer is baked, dynamic links will be
  invalidated.

  Args:
    context: The Django template context. Used to extract the optional _cache
        and _link_template arguments.
    entity: The entity whose sibling is being constructed.
    offset: The signed distance between the entity and its sibling (e.g. 1 for
        next, -1 for previous). The offset will wrap around the siblings list.
    link_type: The type of link to create, e.g. "balloon" or "flyTo".

  Returns:
    A string that can be used in the HREF attribute of an HTML <a> link.

  Raises:
    ValueError: If the specified entity is in an auto managed layer.
  """
  if entity.layer.auto_managed:
    raise ValueError('Cannot create links to entities in auto-managed layers.')
  if not entity:
    return ''

  resolve = template.django.template.resolve_variable
  try:
    cache = resolve('_cache', context)
  except template.django.template.VariableDoesNotExist:
    cache = None
  try:
    link_template = resolve('_link_template', context)
  except template.django.template.VariableDoesNotExist:
    link_template = None

  children = _GetEntitySiblings(entity, cache)
  position = children.index((entity.key().id())) + offset
  target = children[position % len(children)]

  return _GetFlyToLink(target, link_type, link_template)


@_ContextSuppliedTag.Register
def NextLink(context, entity, link_type='balloonFlyto'):
  """Returns a link to the entity following the specified one."""
  return _GetOffsetLink(context, entity, 1, link_type)


@_ContextSuppliedTag.Register
def PrevLink(context, entity, link_type='balloonFlyto'):
  """Returns a link to the entity preceding the specified one."""
  return _GetOffsetLink(context, entity, -1, link_type)


@_ContextSuppliedTag.Register
def EntityLink(context, entity, link_type='balloonFlyto'):
  """Returns a link to a specified entity."""
  if not entity:
    return ''
  resolve = template.django.template.resolve_variable
  try:
    link_template = resolve('_link_template', context)
  except template.django.template.VariableDoesNotExist:
    link_template = None
  return _GetFlyToLink(entity.key().id(), link_type, link_template)


@register.simple_tag
def ResourceLink(resource_id):
  """Returns a link to a specified resource."""
  if not resource_id:
    return ''
  return util.GetInstance(model.Resource, resource_id).GetURL().encode('utf8')


@register.filter
def PrettifyCoordinates180(location):
  """Nicely formats a db.GeoPt, showing longitude as a value in [-180, 180]."""
  arguments = (abs(location.lat), 'NS'[location.lat < 0],
               abs(location.lon), 'EW'[location.lon < 0])
  return '%0.2f&deg;%s %0.2f&deg;%s' % arguments


@register.filter
def PrettifyCoordinates360(location):
  """Nicely formats a db.GeoPt, showing longitude as a value in [0, 360]."""
  longitude = location.lon
  if longitude < 0: longitude += 360
  arguments = (abs(location.lat), 'NS'[location.lat < 0], longitude)
  return '%0.2f&deg;%s %0.2f&deg;E' % arguments


@register.filter
def KilometerToMile(kilometers):
  """Converts kilometres to miles."""
  return kilometers * 0.621371192
