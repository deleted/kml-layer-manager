#!/usr/bin/python2.5
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

"""Small and medium tests for the baking handler."""


from google.appengine import runtime
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from handlers import baker
from lib.mox import mox
import model
import settings
import util


class BakerAndApprenticeTest(mox.MoxTestBase):

  def testCreateFailure(self):
    handler = baker.Baker()
    layer = model.Layer(name='a', world='earth', auto_managed=False)
    layer.put()
    self.assertRaises(util.BadRequest, handler.Create, layer)

  def testCreateSuccess(self):
    self.mox.StubOutWithMock(taskqueue, 'add', use_mock_anything=True)
    self.mox.StubOutWithMock(baker, '_GetBakerURL')
    handler = baker.Baker()
    layer = model.Layer(name='a', world='earth', auto_managed=True)
    layer.put()
    dummy_url = object()

    baker._GetBakerURL(layer).AndReturn(dummy_url)
    taskqueue.add(url=dummy_url, params={'stage': 'setup'})

    self.mox.ReplayAll()

    handler.Create(layer)

  def testUpdate(self):
    self.mox.StubOutWithMock(baker, '_PrepareLayerForBaking')
    self.mox.StubOutWithMock(baker, '_CheckIfLayerIsDone')
    self.mox.StubOutWithMock(baker, '_Subdivide')
    self.mox.StubOutWithMock(model.Division, 'get_by_id')
    handler = baker.BakerApprentice()
    dummy_layer = object()
    dummy_parent = object()
    dummy_retry_division = object()

    baker._PrepareLayerForBaking(dummy_layer)

    baker._CheckIfLayerIsDone(dummy_layer)

    model.Division.get_by_id(123).AndReturn(dummy_parent)
    model.Division.get_by_id(456).AndReturn(dummy_retry_division)
    baker._Subdivide(dummy_layer, 1.23, 4.56, 7.89, 0.36,
                     dummy_parent, dummy_retry_division, False)

    self.mox.ReplayAll()

    handler.request = {'stage': 'invalid'}
    self.assertRaises(util.BadRequest, handler.Update, dummy_layer)

    handler.request = {'stage': 'setup'}
    handler.Update(dummy_layer)

    handler.request = {'stage': 'monitor'}
    handler.Update(dummy_layer)

    handler.request = {
        'stage': 'subdivide',
        'north': '1.23',
        'south': '4.56',
        'east': '7.89',
        'west': '0.36',
        'parent': '123',
        'retry_division': '456',
        'retry_has_children': '',
    }
    handler.Update(dummy_layer)


class BakerStepsTest(mox.MoxTestBase):

  def testPrepareLayerForBakingSuccess(self):
    self.mox.StubOutWithMock(taskqueue, 'add')
    self.mox.StubOutWithMock(baker, '_GetBakerURL')
    mock_divisions = [self.mox.CreateMock(model.Division) for _ in xrange(2)]
    mock_division_query = self.mox.CreateMockAnything()
    mock_entity_query = self.mox.CreateMockAnything()
    mock_entities = [self.mox.CreateMock(model.Entity) for _ in xrange(2)]
    mock_entities[0].baked = True
    mock_entities[1].baked = True
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.division_set = mock_division_query
    mock_layer.entity_set = mock_entity_query
    dummy_url = object()
    dummy_division_cursor = object()
    dummy_entity_cursor = object()

    mock_division_query.fetch(1000).AndReturn(mock_divisions[:1])
    mock_divisions[0].delete()
    mock_division_query.cursor().AndReturn(dummy_division_cursor)
    mock_division_query.with_cursor(dummy_division_cursor).AndReturn(
        mock_division_query)
    mock_division_query.fetch(1000).AndReturn(mock_divisions[1:])
    mock_divisions[1].delete()
    mock_division_query.cursor().AndReturn(dummy_division_cursor)
    mock_division_query.with_cursor(dummy_division_cursor).AndReturn(
        mock_division_query)
    mock_division_query.fetch(1000).AndReturn([])

    mock_entity_query.filter('baked', True).AndReturn(mock_entity_query)
    mock_entity_query.fetch(1000).AndReturn(mock_entities)
    mock_entities[0].put()
    mock_entities[1].put()
    mock_entity_query.cursor().AndReturn(dummy_entity_cursor)
    mock_entity_query.with_cursor(dummy_entity_cursor).AndReturn(
        mock_entity_query)
    mock_entity_query.fetch(1000).AndReturn([])

    baker._GetBakerURL(mock_layer).AndReturn(dummy_url)
    baker._GetBakerURL(mock_layer).AndReturn(dummy_url)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide',
        'north': 90,
        'south': -90,
        'east': 180,
        'west': -180
    })
    taskqueue.add(url=dummy_url, params={'stage': 'monitor'},
                  countdown=settings.BAKER_MONITOR_DELAY)

    self.mox.ReplayAll()

    baker._PrepareLayerForBaking(mock_layer)
    self.assertEqual(mock_entities[0].baked, None)
    self.assertEqual(mock_entities[1].baked, None)

  def testPrepareLayerForBakingInterrupt(self):
    self.mox.StubOutWithMock(taskqueue, 'add')
    self.mox.StubOutWithMock(baker, '_GetBakerURL')
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.division_set = self.mox.CreateMockAnything()
    dummy_url = object()

    mock_layer.division_set.fetch(1000).AndRaise(runtime.DeadlineExceededError)
    baker._GetBakerURL(mock_layer).AndReturn(dummy_url)
    taskqueue.add(url=dummy_url, params={'stage': 'setup'})

    self.mox.ReplayAll()

    baker._PrepareLayerForBaking(mock_layer)

  def testCheckIfLayerIsDoneWhenLayerIsDone(self):
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.entity_set = self.mox.CreateMockAnything()
    mock_query = self.mox.CreateMockAnything()

    mock_layer.entity_set.filter('baked', None).AndReturn(mock_query)
    mock_query.get().AndReturn(None)
    mock_layer.put()

    self.mox.ReplayAll()
    baker._CheckIfLayerIsDone(mock_layer)
    self.assertEqual(mock_layer.baked, True)
    self.assertEqual(mock_layer.busy, False)

  def testCheckIfLayerIsDoneWhenLayerIsNotDone(self):
    self.mox.StubOutWithMock(taskqueue, 'add')
    self.mox.StubOutWithMock(baker, '_GetBakerURL')
    mock_layer = self.mox.CreateMockAnything()
    mock_layer.entity_set = self.mox.CreateMockAnything()
    mock_query = self.mox.CreateMockAnything()
    dummy_url = object()

    mock_layer.entity_set.filter('baked', None).AndReturn(mock_query)
    mock_query.get().AndReturn(object())
    baker._GetBakerURL(mock_layer).AndReturn(dummy_url)
    taskqueue.add(url=dummy_url, params={'stage': 'monitor'},
                  countdown=settings.BAKER_MONITOR_DELAY)

    self.mox.ReplayAll()
    baker._CheckIfLayerIsDone(mock_layer)

  # TODO: Something more sane.
  # TODO: Test for non-maximum results.
  def testSubdivideFreshSuccessWithMaximumResults(self):
    self.mox.StubOutWithMock(baker, '_ScheduleSubdivideChildren')
    self.mox.StubOutWithMock(model, 'Division')
    self.mox.StubOutWithMock(model.Entity, 'bounding_box_fetch')
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.division_set = self.mox.CreateMockAnything()
    mock_layer.entity_set = self.mox.CreateMockAnything()
    mock_layer.division_size = 41
    mock_division = self.mox.CreateMockAnything()
    mock_parent = self.mox.CreateMockAnything()
    max_results = int(41 * (1 + settings.DIVISION_SIZE_GROWTH_LIMIT)) + 1
    mock_entities = [self.mox.CreateMockAnything() for _ in xrange(max_results)]
    for mock_entity in mock_entities:
      mock_entity.baked = False
    mock_query = self.mox.CreateMockAnything()
    dummy_ordered_query = object()
    dummy_id = object()

    @mox.Func
    def VerifyBox(box):
      self.assertEqual(box.north, 4)
      self.assertEqual(box.south, 3)
      self.assertEqual(box.east, 2)
      self.assertEqual(box.west, 1)
      return True

    mock_layer.division_set.filter('north', 4).AndReturn(
        mock_layer.division_set)
    mock_layer.division_set.filter('south', 3).AndReturn(
        mock_layer.division_set)
    mock_layer.division_set.filter('east', 2).AndReturn(mock_layer.division_set)
    mock_layer.division_set.filter('west', 1).AndReturn(mock_layer.division_set)
    mock_layer.division_set.get().AndReturn(None)

    mock_layer.entity_set.filter('baked', None).AndReturn(mock_query)
    mock_query.order('-priority').AndReturn(dummy_ordered_query)
    model.Entity.bounding_box_fetch(
        dummy_ordered_query, VerifyBox, max_results).AndReturn(mock_entities)
    for mock_entity in mock_entities[:41]:
      mock_entity.key().AndReturn(mock_entity)
      mock_entity.id().AndReturn(dummy_id)
    dummy_ids = [dummy_id for _ in xrange(41)]
    model.Division(layer=mock_layer, north=4, south=3, east=2, west=1,
                   entities=dummy_ids, parent_division=mock_parent,
                   baked=False).AndReturn(mock_division)
    mock_division.put()
    for mock_entity in mock_entities[:41]:
      mock_entity.put()
    mock_parent.ClearCache()
    mock_division.put()
    mock_division.GenerateKML()
    baker._ScheduleSubdivideChildren(mock_layer, 4, 3, 2, 1, mock_division)

    self.mox.ReplayAll()
    baker._Subdivide(mock_layer, 4, 3, 2, 1, mock_parent, None, False)
    self.assertEqual(mock_entities[0].baked, True)
    self.assertEqual(mock_entities[1].baked, True)
    self.assertEqual(mock_entities[2].baked, True)
    self.assertEqual(mock_division.baked, True)

  def testSubdivideRetrySuccess(self):
    self.mox.StubOutWithMock(baker, '_ScheduleSubdivideChildren')
    self.mox.StubOutWithMock(model.Entity, 'get_by_id')
    layer = model.Layer(name='a', world='earth', auto_managed=True)
    layer.put()
    mock_division = self.mox.CreateMock(model.Division)
    mock_division.entities = object()
    mock_division.north = 1
    mock_division.south = 2
    mock_division.east = 3
    mock_division.west = 4
    mock_entities = [self.mox.CreateMock(model.Entity) for _ in xrange(3)]
    mock_entities[0].baked = False
    mock_entities[1].baked = True
    mock_entities[2].baked = False

    model.Entity.get_by_id(mock_division.entities).AndReturn(mock_entities)
    mock_entities[0].put()
    mock_entities[2].put()
    mock_division.put()
    mock_division.GenerateKML()
    baker._ScheduleSubdivideChildren(layer, 1, 2, 3, 4, mock_division)

    self.mox.ReplayAll()
    baker._Subdivide(layer, None, None, None, None, None, mock_division, True)
    self.assertEqual(mock_entities[0].baked, True)
    self.assertEqual(mock_entities[1].baked, True)
    self.assertEqual(mock_entities[2].baked, True)
    self.assertEqual(mock_division.baked, True)

  def testSubdivideCancelRerun(self):
    self.mox.StubOutWithMock(taskqueue, 'add')
    mock_layer = self.mox.CreateMock(model.Layer)
    mock_layer.division_set = self.mox.CreateMockAnything()
    mock_query = self.mox.CreateMockAnything()

    mock_layer.division_set.filter('north', 1).AndReturn(mock_query)
    mock_query.filter('south', 2).AndReturn(mock_query)
    mock_query.filter('east', 3).AndReturn(mock_query)
    mock_query.filter('west', 4).AndReturn(mock_query)
    mock_query.get().AndReturn(object())

    self.mox.ReplayAll()
    baker._Subdivide(mock_layer, 1, 2, 3, 4, None, None, False)
    # Mox makes sure nothing else has been called on the layer or taskqueue.

  def testSubdivideInterruptBeforeSave(self):
    self.mox.StubOutWithMock(model.Entity, 'bounding_box_fetch')
    self.mox.StubOutWithMock(taskqueue, 'add')  # Ensure nothing is added.
    dummy_url = object()
    self.stubs.Set(baker, '_GetBakerURL', lambda _: dummy_url)
    layer = model.Layer(name='a', world='earth', auto_managed=False)
    layer.put()

    model.Entity.bounding_box_fetch(
        mox.IgnoreArg(), mox.IgnoreArg(), mox.IgnoreArg()).AndRaise(
            runtime.DeadlineExceededError)


    self.mox.ReplayAll()
    self.assertRaises(AttributeError, baker._Subdivide,
                      layer, 0, 0, 0, 0, None, None, False)

  def testSubdivideInterruptAfterSave(self):
    self.mox.StubOutWithMock(model.Entity, 'bounding_box_fetch')
    self.mox.StubOutWithMock(taskqueue, 'add')
    dummy_url = object()
    self.stubs.Set(baker, '_GetBakerURL', lambda _: dummy_url)
    layer = model.Layer(name='a', world='earth', auto_managed=False)
    layer.put()
    mock_entity = self.mox.CreateMockAnything()
    mock_entity.key = lambda: mock_key
    mock_entity.baked = False
    mock_key = self.mox.CreateMockAnything()
    mock_key.id = lambda: 42

    @mox.Func
    def VerifyArgs(args):
      self.assertEqual(args['stage'], 'subdivide')
      self.assertEqual(args['retry_division'],
                       model.Division.all().get().key().id())
      self.assertEqual(args['retry_has_children'], '')
      return True

    ignore = mox.IgnoreArg()
    model.Entity.bounding_box_fetch(ignore, ignore, ignore).AndReturn(
        [mock_entity])
    mock_entity.put().AndRaise(db.Error)
    taskqueue.add(url=dummy_url, params=VerifyArgs)

    self.mox.ReplayAll()
    baker._Subdivide(layer, 0.0, 0.0, 0.0, 0.0, None, None, False)

  def testScheduleSubdivideChildren(self):
    dummy_url = object()
    dummy_id = object()
    self.mox.StubOutWithMock(taskqueue, 'add')
    self.stubs.Set(baker, '_GetBakerURL', lambda _: dummy_url)
    mock_key = self.mox.CreateMockAnything()
    mock_key.id = lambda: dummy_id
    mock_parent = self.mox.CreateMock(model.Division)
    mock_parent.key = lambda: mock_key

    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 90, 'south': 0, 'east': 40, 'west': 10
    }).InAnyOrder(1)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 0, 'south': -90, 'east': 40, 'west': 10
    }).InAnyOrder(1)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 90, 'south': 0, 'east': 10, 'west': -20
    }).InAnyOrder(1)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 0, 'south': -90, 'east': 10, 'west': -20
    }).InAnyOrder(1)

    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 90, 'south': 45, 'east': 40, 'west': -20
    }).InAnyOrder(2)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 45, 'south': 0, 'east': 40, 'west': 10
    }).InAnyOrder(2)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 45, 'south': 0, 'east': 10, 'west': -20
    }).InAnyOrder(2)

    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 0, 'south': -45, 'east': 40, 'west': 10
    }).InAnyOrder(3)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 0, 'south': -45, 'east': 10, 'west': -20
    }).InAnyOrder(3)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': -45, 'south': -90, 'east': 40, 'west': -20
    }).InAnyOrder(3)

    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 40, 'south': 0, 'east': 90, 'west': 0
    }).InAnyOrder(4)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 0, 'south': -40, 'east': 90, 'west': 0
    }).InAnyOrder(4)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 40, 'south': 0, 'east': 180, 'west': 90
    }).InAnyOrder(4)
    taskqueue.add(url=dummy_url, params={
        'stage': 'subdivide', 'parent': dummy_id,
        'north': 0, 'south': -40, 'east': 180, 'west': 90
    }).InAnyOrder(4)

    self.mox.ReplayAll()

    # Touches both poles; 4 slices.
    baker._ScheduleSubdivideChildren(object(), 90, -90, 40, -20, mock_parent)
    # Touches one pole; 3 slices.
    baker._ScheduleSubdivideChildren(object(), 90, 0, 40, -20, mock_parent)
    baker._ScheduleSubdivideChildren(object(), 0, -90, 40, -20, mock_parent)
    # Touches no poles; 4 slices.
    baker._ScheduleSubdivideChildren(object(), 40, -40, 180, 0, mock_parent)

  def testGetBakerURL(self):
    layer = model.Layer(name='a', world='earth', auto_managed=True)
    layer_id = layer.put().id()
    self.assertEqual(baker._GetBakerURL(layer), '/baker-update/%d' % layer_id)
    self.assertRaises(AttributeError, baker._GetBakerURL, object())
