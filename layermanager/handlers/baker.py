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

"""The layer auto-regionation mechanism."""

from google.appengine import runtime
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors
import handlers.base
from lib.geo import geotypes
import model
import settings
import util


class Baker(handlers.base.PageHandler):
  """A handler to show a regionation form."""

  PERMISSION_REQUIRED = model.Permission.MANAGE
  FORM_TEMPLATE = 'baker'

  def Create(self, layer):
    """Starts a regionation run on an auto-managed layer."""
    if not layer.auto_managed:
      raise util.BadRequest('Only auto-managed layers can be baked.')
    layer.baked = False
    layer.busy = True
    layer.put()
    layer.ClearCache()
    taskqueue.add(url=_GetBakerURL(layer), params={'stage': 'setup'})


class BakerApprentice(handlers.base.PageHandler):
  """A handler to run regionation tasks.

  This needs to be separate from Baker, the form/creation handler, because it is
  to be called by the queue API which cannot be authenticated as a user and
  therefore has to have PERMISSION_REQUIRED = None. The URL that leads to
  Update(), the sole function in this class, is protected in app.yaml by
  login: admin.
  """

  PERMISSION_REQUIRED = None

  def Update(self, layer):
    """Dispatches a baking task.

    POST Args:
      stage: Which stage is currently being run. Takes one of these values:
        'setup': Reset all entities' baking status and delete all Division
            objects. Reschedules itself if setup can't be completed in one run.
            Once done, schedules the initial subdivide stage and the monitor.
            There should be at most one setup task per layer running at a time.
        'subdivide': Creates a new Division object based on the north, south,
            east, west and parent POST parameters, and schedules further
            subdivide tasks. There may be any number of subdivide tasks running
            in parallel.
        'monitor': Checks whether the baking has finished. If it has, marks the
            layer as baked and not busy. Otherwise reschedules itself.
      north: For subdivide tasks, the maximum latitude of the bounding box.
      south: For subdivide tasks, the minimum latitude of the bounding box.
      east: For subdivide tasks, the maximum longitude of the bounding box.
      west: For subdivide tasks, the minimum longitude of the bounding box.
      parent: For subdivide tasks, the ID of the parent Division. Empty for root
          divisions.
      retry_division: The ID of a division to try processing again. Only
          specified for subdivide tasks that previously failed due to time
          constraints.
      retry_has_children: Whether this subdivision should be subdivided further.
          Only specified for subdivide tasks that previously failed due to time
          constrains. For normal subdivide tasks, calculated based on datastore
          query results.

    Args:
      layer: The layer to update.
    """
    stage = self.request.get('stage')
    if stage == 'setup':
      # TODO: Parallelize setup. Rebaking is too slow now due to this.
      _PrepareLayerForBaking(layer)
    elif stage == 'monitor':
      _CheckIfLayerIsDone(layer)
    elif stage == 'subdivide':
      try:
        north = self.GetArgument('north', float)
        south = self.GetArgument('south', float)
        east = self.GetArgument('east', float)
        west = self.GetArgument('west', float)
        parent = self.GetArgument('parent', int)
        if parent:
          parent = model.Division.get_by_id(parent)
        else:
          parent = None
        retry_division = self.GetArgument('retry_division', int)
        if retry_division:
          retry_division = model.Division.get_by_id(retry_division)
        else:
          retry_division = None
        retry_has_children = bool(self.request.get('retry_has_children'))
      except (TypeError, ValueError):
        raise util.BadRequest('Invalid baking parameters.')
      _Subdivide(layer, north, south, east, west,
                 parent, retry_division, retry_has_children)
    else:
      raise util.BadRequest('Invalid baking stage.')


def _PrepareLayerForBaking(layer):
  """Prepares the layer for subdivision steps.

  Removes all existing divisions in this layer and clears the baked flag on
  all entities.

  If App Engine interrupts this function before all the preparations are
  finished, it is rescheduled to be called again immediately, where it
  continues from where it left off.

  Once preparations are finished, schedules an initial subdivision step to be
  run immediately and a monitoring check to be run after
  settings.BAKER_MONITOR_DELAY seconds.

  Args:
    layer: The layer to prepare.
  """
  try:
    division_query = layer.division_set
    while True:
      divisions = division_query.fetch(1000)
      if not divisions:
        break
      for division in divisions:
        division.delete()
      division_query.with_cursor(division_query.cursor())

    entity_query = layer.entity_set.filter('baked', True)
    while True:
      entities = entity_query.fetch(1000)
      if not entities:
        break
      for entity in entities:
        entity.baked = None
        entity.put()
      entity_query.with_cursor(entity_query.cursor())
  except (runtime.DeadlineExceededError, db.Error,
          apiproxy_errors.OverQuotaError):
    taskqueue.add(url=_GetBakerURL(layer), params={'stage': 'setup'})
  else:
    args = {
        'stage': 'subdivide',
        'north': 90,
        'south': -90,
        'east': 180,
        'west': -180
    }
    taskqueue.add(url=_GetBakerURL(layer), params=args)

    args = {'stage': 'monitor'}
    taskqueue.add(url=_GetBakerURL(layer), params=args,
                  countdown=settings.BAKER_MONITOR_DELAY)


def _CheckIfLayerIsDone(layer):
  """Checks whether a layer has finished baking.

  Checks whether there are any entities in the layer that have not been marked
  as baked yet. If there are, reschedules a new monitoring check after
  settings.BAKER_MONITOR_DELAY seconds. Otherwise sets the layer's baked
  flag and clears its busy flag.

  Args:
    layer: The layer to check.
  """
  if layer.entity_set.filter('baked', None).get():
    args = {'stage': 'monitor'}
    taskqueue.add(url=_GetBakerURL(layer), params=args,
                  countdown=settings.BAKER_MONITOR_DELAY)
  else:
    layer.baked = True
    layer.busy = False
    layer.put()


def _Subdivide(layer, north, south, east, west,
               parent, retry_division, retry_has_children):
  """Performs a subdivision step.

  Either starts a new subdivision or completes a previously interrupted one.
  If the function is interrupted, reschedules itself immediately. If the
  geospatial query has completed before the interruption, its results are
  saved and not recalculated.

  Gets the most prioritized N entities in the specified bounding box, and puts
  them in a new Division object. If the number of entities is above the hard
  maximum, limits the number of entities in the new division to the soft
  maximum and schedules further subdivisions immediately. Otherwise puts all
  the entities in the new division and does not schedule any further actions.

  Args:
    layer: The layer to subdivide.
    north: The maximum latitude of the region to subdivide.
    south: The minimum latitude of the region to subdivide.
    east: The maximum longitude of the region to subdivide.
    west: the minimum longitude of the region to subdivide.
    parent: The parent Division. None for root divisions.
    retry_division: The division to try processing again. Only specified for
        subdivide tasks that previously failed due to time constraints.
    retry_has_children: Whether this subdivision should be subdivided further.
        Only specified for subdivide tasks that previously failed due to time
        constrains. For normal subdivide tasks, calculated based on datastore
        query results.
  """
  query = layer.division_set.filter('north', north).filter('south', south)
  query = query.filter('east', east).filter('west', west)
  if query.get():
    # This was an unscheduled rerun. Cancel it.
    return

  division_size = (layer.division_size or settings.DEFAULT_DIVISION_SIZE)
  ratio = (1 + settings.DIVISION_SIZE_GROWTH_LIMIT)
  max_results = int(division_size * ratio) + 1

  has_children = False
  division = None

  try:
    if retry_division:
      division = retry_division
      entities = model.Entity.get_by_id(division.entities)
      has_children = retry_has_children
      north = division.north
      south = division.south
      east = division.east
      west = division.west
    else:
      box = geotypes.Box(north, east, south, west)
      entities = layer.entity_set.filter('baked', None).order('-priority')
      entities = model.Entity.bounding_box_fetch(entities, box, max_results)
      if not entities:
        return
      has_children = (len(entities) == max_results)
      if has_children:
        entities = entities[:division_size]
      entity_ids = [i.key().id() for i in entities]

      division = model.Division(layer=layer, north=north, south=south,
                                east=east, west=west, entities=entity_ids,
                                parent_division=parent, baked=False)
      division.put()

    for entity in entities:
      if not entity.baked:
        entity.baked = True
        entity.put()

    if parent: parent.ClearCache()
    division.baked = True
    division.put()
    division.GenerateKML()  # Build KML cache.
  except (runtime.DeadlineExceededError, db.Error,
          apiproxy_errors.OverQuotaError):
    # If division does not exist or isn't saved, this raises an error and causes
    # the request to be rescheduled with the original parameters.
    retry_division_id = division.key().id()
    if retry_division_id:
      taskqueue.add(url=_GetBakerURL(layer), params={
          'stage': 'subdivide',
          'retry_division': retry_division_id,
          'retry_has_children': '1'[:has_children]
      })
    else:
      raise
  else:
    try:
      if has_children:
        _ScheduleSubdivideChildren(layer, north, south, east, west, division)
    except runtime.DeadlineExceededError:
      if has_children:
        _ScheduleSubdivideChildren(layer, north, south, east, west, division)


def _ScheduleSubdivideChildren(layer, north, south, east, west, parent):
  """Schedules subdivide steps for each part of the specified region.

  If the bounding box touches either of the poles on one side (and only one
  side), divides it into 3 parts, where the part that touches the pole spans all
  the way the entire longitude range, while the other two parts span half of
  that.

  Args:
    layer: The layer for which to schedule further subdivide steps.
    north: The maximum latitude of the region to subdivide.
    south: The minimum latitude of the region to subdivide.
    east: The maximum longitude of the region to subdivide.
    west: the minimum longitude of the region to subdivide.
    parent: The Division object which covers the entire region.
  """
  mid_latitude = (north + south) / 2
  mid_longitude = (east + west) / 2
  if north == 90 and south != -90:
    slices = (
        {'north': north, 'south': mid_latitude,
         'east': east, 'west': west},
        {'north': mid_latitude, 'south': south,
         'east': east, 'west': mid_longitude},
        {'north': mid_latitude, 'south': south,
         'east': mid_longitude, 'west': west}
    )
  elif south == -90 and north != 90:
    slices = (
        {'north': north, 'south': mid_latitude,
         'east': east, 'west': mid_longitude},
        {'north': mid_latitude, 'south': south,
         'east': east, 'west': west},
        {'north': north, 'south': mid_latitude,
         'east': mid_longitude, 'west': west},
    )
  else:
    slices = (
        {'north': north, 'south': mid_latitude,
         'east': east, 'west': mid_longitude},
        {'north': mid_latitude, 'south': south,
         'east': east, 'west': mid_longitude},
        {'north': north, 'south': mid_latitude,
         'east': mid_longitude, 'west': west},
        {'north': mid_latitude, 'south': south,
         'east': mid_longitude, 'west': west}
    )
  args = {'stage': 'subdivide', 'parent': parent.key().id()}
  for slice_args in slices:
    args.update(slice_args)
    taskqueue.add(url=_GetBakerURL(layer), params=args)


def _GetBakerURL(layer):
  return '/baker-update/%d' % layer.key().id()
