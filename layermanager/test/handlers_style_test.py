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

"""Medium tests for the Style handler."""


import StringIO
from handlers import style
from lib.mox import mox
import model
import util


class StyleHandlerTest(mox.MoxTestBase):

  def testDeleteSuccess(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = style.StyleHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_style = self.mox.CreateMock(model.Style)
    mock_style.entity_set = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_id = object()

    handler.request.get('style_id').AndReturn(dummy_id)
    util.GetInstance(model.Style, dummy_id, dummy_layer).AndReturn(mock_style)
    mock_style.entity_set.get().AndReturn(None)
    mock_style.delete()

    self.mox.ReplayAll()
    handler.Delete(dummy_layer)

  def testDeleteFailure(self):
    self.mox.StubOutWithMock(util, 'GetInstance')
    handler = style.StyleHandler()
    handler.request = self.mox.CreateMockAnything()
    mock_style = self.mox.CreateMock(model.Style)
    mock_style.entity_set = self.mox.CreateMockAnything()
    dummy_layer = object()
    dummy_id = object()

    # Simulate GetInstance() not finding the style.
    handler.request.get('style_id').AndReturn(dummy_id)
    util.GetInstance(model.Style, dummy_id, dummy_layer).AndRaise(
        util.BadRequest)

    # Simulate an entity referencing the style.
    handler.request.get('style_id').AndReturn(dummy_id)
    util.GetInstance(model.Style, dummy_id, dummy_layer).AndReturn(mock_style)
    mock_style.entity_set.get().AndReturn(object())

    self.mox.ReplayAll()
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)
    self.assertRaises(util.BadRequest, handler.Delete, dummy_layer)

  def testCreateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    highlight_icon = model.Resource(layer=layer, type='icon', filename='c')
    highlight_icon_id = highlight_icon.put().id()

    handler = style.StyleHandler()
    handler.request = {
        'name': 'fabulous',
        'has_highlight': 'yes',
        'icon': str(icon_id),
        'icon_color': 'AABBCCDD',
        'icon_scale': '1',
        'icon_heading': '2.3',
        'label_color': 'DeadBeef',
        'label_scale': '3.4',
        'balloon_color': '900d900d',
        'text_color': '1337d00d',
        'line_color': '900dbeef',
        'line_width': '4',
        'polygon_color': '11223344',
        'polygon_fill': '1',
        'polygon_outline': 'False',
        'highlight_icon': str(highlight_icon_id),
        'highlight_icon_color': '22334455',
        'highlight_icon_scale': '5.6',
        # highlight_icon_heading unspecified.
        'highlight_label_color': '',
        'highlight_label_scale': '',
        'highlight_balloon_color': '44556677',
        'highlight_text_color': '55667788',
        'highlight_line_color': '66778899',
        'highlight_line_width': '8',
        'highlight_polygon_color': '77889900',
        # highlight_polygon_fill unspecified.
        'highlight_polygon_outline': '',
    }
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Style.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'fabulous')
    self.assertEqual(result.has_highlight, True)
    self.assertEqual(result.icon.key().id(), icon_id)
    self.assertEqual(result.icon_color, 'AABBCCDD')
    self.assertEqual(result.icon_scale, 1)
    self.assertEqual(result.icon_heading, 2.3)
    self.assertEqual(result.label_color, 'DeadBeef')
    self.assertEqual(result.label_scale, 3.4)
    self.assertEqual(result.balloon_color, '900d900d')
    self.assertEqual(result.text_color, '1337d00d')
    self.assertEqual(result.line_color, '900dbeef')
    self.assertEqual(result.line_width, 4)
    self.assertEqual(result.polygon_color, '11223344')
    self.assertEqual(result.polygon_fill, True)
    self.assertEqual(result.polygon_outline, True)
    self.assertEqual(result.highlight_icon.key().id(), highlight_icon_id)
    self.assertEqual(result.highlight_icon_color, '22334455')
    self.assertEqual(result.highlight_icon_scale, 5.6)
    self.assertEqual(result.highlight_icon_heading, None)
    self.assertEqual(result.highlight_label_color, None)
    self.assertEqual(result.highlight_label_scale, None)
    self.assertEqual(result.highlight_balloon_color, '44556677')
    self.assertEqual(result.highlight_text_color, '55667788')
    self.assertEqual(result.highlight_line_color, '66778899')
    self.assertEqual(result.highlight_line_width, 8)
    self.assertEqual(result.highlight_polygon_color, '77889900')
    self.assertEqual(result.highlight_polygon_fill, None)
    self.assertEqual(result.highlight_polygon_outline, None)

  def testCreateHighlightlessSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()

    handler = style.StyleHandler()
    handler.request = {
        'name': 'abc',
        'has_highlight': '',
        'icon_scale': '1',
        'icon_heading': '2.3',
        'highlight_balloon_color': '44556677',
    }
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Style.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.has_highlight, False)
    self.assertEqual(result.icon_scale, 1)
    self.assertEqual(result.icon_heading, 2.3)
    # Make sure unspecified normal properties are unset.
    self.assertEqual(result.icon, None)
    self.assertEqual(result.icon_color, None)
    # Make sure unspecified highlight properties are unset.
    self.assertEqual(result.highlight_balloon_color, None)
    # Make sure Boolean highlight properties are unset.
    self.assertEqual(result.highlight_polygon_fill, None)

  def testCreateMinimalSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()

    handler = style.StyleHandler()
    handler.request = {'name': 'abc'}
    handler.response = self.mox.CreateMockAnything()
    handler.response.out = StringIO.StringIO()

    handler.Create(layer)
    result = model.Style.get_by_id(int(handler.response.out.getvalue()))
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'abc')
    self.assertEqual(result.has_highlight, False)
    self.assertEqual(result.icon, None)
    self.assertEqual(result.icon_scale, None)
    self.assertEqual(result.polygon_fill, None)
    self.assertEqual(result.highlight_balloon_color, None)
    self.assertEqual(result.highlight_polygon_fill, None)

  def testCreateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='a', world='earth')
    other_layer.put()
    bad_icon = model.Resource(layer=layer, type='image', filename='a')
    bad_icon_id = bad_icon.put().id()
    foreign_icon = model.Resource(layer=other_layer, type='icon', filename='b')
    foreign_icon_id = foreign_icon.put().id()

    handler = style.StyleHandler()

    # Empty name.
    handler.request = {'name': ''}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Overly long name.
    handler.request = {'name': 'ab' * 600}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Non-icon resource as an icon.
    handler.request = {'name': 'ab', 'icon': bad_icon_id}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Icon from another layer.
    handler.request = {'name': 'ab', 'icon': foreign_icon_id}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid character in color.
    handler.request = {'name': 'ab', 'icon_color': '0000000g'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Color string too short.
    handler.request = {'name': 'ab', 'icon_color': '112233'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Color string too long.
    handler.request = {'name': 'ab', 'icon_color': '1122334455'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid float property.
    handler.request = {'name': 'ab', 'icon_scale': 'a'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Partly invalid float property.
    handler.request = {'name': 'ab', 'icon_scale': '1.5a'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Float value for integer property.
    handler.request = {'name': 'ab', 'line_width': '1.5'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

    # Invalid integer property.
    handler.request = {'name': 'ab', 'line_width': 'a'}
    self.assertRaises(util.BadRequest, handler.Create, layer)

  def testUpdateCompleteSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    highlight_icon = model.Resource(layer=layer, type='icon', filename='c')
    highlight_icon_id = highlight_icon.put().id()
    style_to_update = model.Style(
        layer=layer, name='a', has_highlight=True, icon=icon,
        icon_color='AABBCC01', icon_scale=11.0, icon_heading=12.3,
        label_color='AABBCC02', label_scale=13.4, balloon_color='AABBCC03',
        text_color='AABBCC04', line_color='AABBCC05', line_width=14,
        polygon_color='AABBCC06', polygon_fill=True, polygon_outline=False,
        highlight_icon=None, highlight_icon_color='AABBCC07',
        highlight_icon_scale=15.6, highlight_icon_heading=99.0,
        highlight_label_color=None, highlight_label_scale=17.89,
        highlight_balloon_color='AABBCC08', highlight_text_color='AABBCC09',
        highlight_line_color='AABBCC10', highlight_line_width=18,
        highlight_polygon_color='AABBCC11', highlight_polygon_fill=False,
        highlight_polygon_outline=True)
    style_id = style_to_update.put().id()

    handler = style.StyleHandler()
    handler.request = {
        'style_id': style_id,
        'name': 'fabulous',
        'has_highlight': 'yes',
        'icon': str(icon_id),
        'icon_color': 'AABBCCDD',
        'icon_scale': '1',
        'icon_heading': '2.3',
        'label_color': 'DeadBeef',
        'label_scale': '3.4',
        'balloon_color': '900d900d',
        'text_color': '1337d00d',
        'line_color': '900dbeef',
        'line_width': '4',
        'polygon_color': '11223344',
        'polygon_fill': '1',
        # polygon_outline unspecified.
        'highlight_icon': str(highlight_icon_id),
        'highlight_icon_color': '22334455',
        'highlight_icon_scale': '5.6',
        # highlight_icon_heading unspecified.
        'highlight_label_color': '',
        'highlight_label_scale': '',
        'highlight_balloon_color': '44556677',
        'highlight_text_color': '55667788',
        'highlight_line_color': '66778899',
        'highlight_line_width': '8',
        'highlight_polygon_color': '77889900',
        # highlight_polygon_fill unspecified.
        'highlight_polygon_outline': '',
    }
    handler.Update(layer)
    result = model.Style.get_by_id(style_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'fabulous')
    self.assertEqual(result.has_highlight, True)
    self.assertEqual(result.icon.key().id(), icon_id)
    self.assertEqual(result.icon_color, 'AABBCCDD')
    self.assertEqual(result.icon_scale, 1)
    self.assertEqual(result.icon_heading, 2.3)
    self.assertEqual(result.label_color, 'DeadBeef')
    self.assertEqual(result.label_scale, 3.4)
    self.assertEqual(result.balloon_color, '900d900d')
    self.assertEqual(result.text_color, '1337d00d')
    self.assertEqual(result.line_color, '900dbeef')
    self.assertEqual(result.line_width, 4)
    self.assertEqual(result.polygon_color, '11223344')
    self.assertEqual(result.polygon_fill, True)
    self.assertEqual(result.polygon_outline, False)
    self.assertEqual(result.highlight_icon.key().id(), highlight_icon_id)
    self.assertEqual(result.highlight_icon_color, '22334455')
    self.assertEqual(result.highlight_icon_scale, 5.6)
    self.assertEqual(result.highlight_icon_heading, 99)
    self.assertEqual(result.highlight_label_color, None)
    self.assertEqual(result.highlight_label_scale, None)
    self.assertEqual(result.highlight_balloon_color, '44556677')
    self.assertEqual(result.highlight_text_color, '55667788')
    self.assertEqual(result.highlight_line_color, '66778899')
    self.assertEqual(result.highlight_line_width, 8)
    self.assertEqual(result.highlight_polygon_color, '77889900')
    self.assertEqual(result.highlight_polygon_fill, False)
    self.assertEqual(result.highlight_polygon_outline, None)

  def testUpdateNoOpSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    style_to_update = model.Style(layer=layer, name='a', icon=icon,
                                  icon_color='AABBCC01', line_width=14,
                                  highlight_icon_heading=99.0,
                                  highlight_polygon_fill=False)
    style_id = style_to_update.put().id()

    handler = style.StyleHandler()
    handler.request = {'style_id': style_id}
    handler.Update(layer)
    result = model.Style.get_by_id(style_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'a')
    self.assertEqual(result.has_highlight, False)
    self.assertEqual(result.icon.put().id(), icon_id)
    self.assertEqual(result.icon_color, 'AABBCC01')
    self.assertEqual(result.icon_scale, None)
    self.assertEqual(result.icon_heading, None)
    self.assertEqual(result.label_color, None)
    self.assertEqual(result.label_scale, None)
    self.assertEqual(result.balloon_color, None)
    self.assertEqual(result.text_color, None)
    self.assertEqual(result.line_color, None)
    self.assertEqual(result.line_width, 14)
    self.assertEqual(result.polygon_color, None)
    self.assertEqual(result.polygon_fill, None)
    self.assertEqual(result.polygon_outline, None)
    self.assertEqual(result.highlight_icon, None)
    self.assertEqual(result.highlight_icon_color, None)
    self.assertEqual(result.highlight_icon_scale, None)
    self.assertEqual(result.highlight_icon_heading, 99.0)
    self.assertEqual(result.highlight_label_color, None)
    self.assertEqual(result.highlight_label_scale, None)
    self.assertEqual(result.highlight_balloon_color, None)
    self.assertEqual(result.highlight_text_color, None)
    self.assertEqual(result.highlight_line_color, None)
    self.assertEqual(result.highlight_line_width, None)
    self.assertEqual(result.highlight_polygon_color, None)
    self.assertEqual(result.highlight_polygon_fill, False)
    self.assertEqual(result.highlight_polygon_outline, None)

  def testUpdateUnhighlightSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer_id = layer.put().id()
    icon = model.Resource(layer=layer, type='icon', filename='b')
    icon_id = icon.put().id()
    style_to_update = model.Style(layer=layer, name='a', icon=icon,
                                  has_highlight=True, icon_color='AABBCC01',
                                  line_width=14, highlight_icon_heading=99.0,
                                  highlight_polygon_fill=False)
    style_id = style_to_update.put().id()

    handler = style.StyleHandler()
    handler.request = {'style_id': style_id, 'has_highlight': ''}
    handler.Update(layer)
    result = model.Style.get_by_id(style_id)
    self.assertEqual(result.layer.key().id(), layer_id)
    self.assertEqual(result.name, 'a')
    self.assertEqual(result.has_highlight, None)
    self.assertEqual(result.icon.put().id(), icon_id)
    self.assertEqual(result.icon_color, 'AABBCC01')
    self.assertEqual(result.icon_scale, None)
    self.assertEqual(result.icon_heading, None)
    self.assertEqual(result.label_color, None)
    self.assertEqual(result.label_scale, None)
    self.assertEqual(result.balloon_color, None)
    self.assertEqual(result.text_color, None)
    self.assertEqual(result.line_color, None)
    self.assertEqual(result.line_width, 14)
    self.assertEqual(result.polygon_color, None)
    self.assertEqual(result.polygon_fill, None)
    self.assertEqual(result.polygon_outline, None)
    self.assertEqual(result.highlight_icon, None)
    self.assertEqual(result.highlight_icon_color, None)
    self.assertEqual(result.highlight_icon_scale, None)
    self.assertEqual(result.highlight_icon_heading, 99.0)
    self.assertEqual(result.highlight_label_color, None)
    self.assertEqual(result.highlight_label_scale, None)
    self.assertEqual(result.highlight_balloon_color, None)
    self.assertEqual(result.highlight_text_color, None)
    self.assertEqual(result.highlight_line_color, None)
    self.assertEqual(result.highlight_line_width, None)
    self.assertEqual(result.highlight_polygon_color, None)
    self.assertEqual(result.highlight_polygon_fill, False)
    self.assertEqual(result.highlight_polygon_outline, None)

  def testUpdateHighlightFieldInUnhighlightedSuccess(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    style_to_update = model.Style(layer=layer, name='a', has_highlight=False,
                                  icon_color='00112233',
                                  highlight_icon_color='AABBCCDD')
    style_id = style_to_update.put().id()

    handler = style.StyleHandler()
    handler.request = {'style_id': style_id, 'highlight_icon_color': '88888888'}
    handler.Update(layer)
    result = model.Style.get_by_id(style_id)
    self.assertEqual(result.has_highlight, False)
    self.assertEqual(result.icon_color, '00112233')
    self.assertEqual(result.highlight_icon_color, '88888888')

  def testUpdateFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    other_layer = model.Layer(name='a', world='earth')
    other_layer.put()
    bad_icon = model.Resource(layer=layer, type='image', filename='a')
    bad_icon_id = bad_icon.put().id()
    foreign_icon = model.Resource(layer=other_layer, type='icon', filename='b')
    foreign_icon_id = foreign_icon.put().id()
    style_id = model.Style(layer=layer, name='a').put().id()

    handler = style.StyleHandler()

    # No style ID.
    handler.request = {'name': 'ab'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Empty name.
    handler.request = {'style_id': style_id, 'name': ''}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Overly long name.
    handler.request = {'style_id': style_id, 'name': 'ab' * 600}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Non-icon resource as an icon.
    handler.request = {'style_id': style_id, 'name': 'ab',
                       'icon': bad_icon_id}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Icon from another layer.
    handler.request = {'style_id': style_id, 'name': 'ab',
                       'icon': foreign_icon_id}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid character in color string.
    handler.request = {'style_id': style_id, 'name': 'ab',
                       'icon_color': '0000000g'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Color string too short.
    handler.request = {'style_id': style_id, 'name': 'ab',
                       'icon_color': '112233'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Color string too long.
    handler.request = {'style_id': style_id, 'name': 'ab',
                       'icon_color': '1122334455'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid float property.
    handler.request = {'style_id': style_id, 'name': 'ab', 'icon_scale': 'a'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Partly invalid float property.
    handler.request = {'style_id': style_id, 'name': 'ab', 'icon_scale': '1.5a'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Float value for integer property.
    handler.request = {'style_id': style_id, 'name': 'ab', 'line_width': '1.5'}
    self.assertRaises(util.BadRequest, handler.Update, layer)

    # Invalid integer property.
    handler.request = {'style_id': style_id, 'name': 'ab', 'line_width': 'a'}
    self.assertRaises(util.BadRequest, handler.Update, layer)
