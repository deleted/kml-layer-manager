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

"""Tests for the KML generation in the layer manager models."""


import re
import unittest
from xml.etree import ElementTree
from google.appengine.ext import db
import model
import settings


def _GetRidOfNamespace(kml_text):
  return re.sub('xmlns(:gx)?=".*?"', '', kml_text)


class PointKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    point = model.Point(location=db.GeoPt(1.1, 2.2), altitude=3.3,
                        altitude_mode='relativeToGround', extrude=True)
    point.put()
    tree = ElementTree.fromstring(point.GenerateKML())

    self.assertEqual(tree.tag, 'Point')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['extrude', 'altitudeMode', 'coordinates'])
    self.assertEqual(tree.find('extrude').text, '1')
    self.assertEqual(tree.find('altitudeMode').text, 'relativeToGround')
    self.assertEqual(tree.find('coordinates').text, '2.2,1.1,3.3')

  def testGenerateMinimalKML(self):
    point = model.Point(location=db.GeoPt(1.11, 2.22))
    point.put()
    tree = ElementTree.fromstring(point.GenerateKML())

    self.assertEqual([i.tag for i in tree.getchildren()], ['coordinates'])
    self.assertEqual(tree.find('coordinates').text, '2.22,1.11,0')


class PolygonKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    outer_points = [db.GeoPt(0, 5), db.GeoPt(5, 0), db.GeoPt(0, -5)]
    inner_points = [db.GeoPt(1, 2), db.GeoPt(2, 1), db.GeoPt(1, -2)]
    polygon = model.Polygon(outer_points=outer_points,
                            inner_points=inner_points,
                            outer_altitudes=[1.0, 2.0, 3.0],
                            inner_altitudes=[2.0, 3.0, 4.0],
                            altitude_mode='absolute',
                            tessellate=True, extrude=False)
    polygon.put()
    tree = ElementTree.fromstring(polygon.GenerateKML())

    self.assertEqual(tree.tag, 'Polygon')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['extrude', 'tessellate', 'altitudeMode',
                      'outerBoundaryIs', 'innerBoundaryIs'])
    self.assertEqual(tree.find('extrude').text, '0')
    self.assertEqual(tree.find('tessellate').text, '1')
    self.assertEqual(tree.find('outerBoundaryIs/LinearRing/coordinates').text,
                     '5.0,0.0,1.0 0.0,5.0,2.0 -5.0,0.0,3.0 5.0,0.0,1.0')
    self.assertEqual(tree.find('innerBoundaryIs/LinearRing/coordinates').text,
                     '2.0,1.0,2.0 1.0,2.0,3.0 -2.0,1.0,4.0 2.0,1.0,2.0')

  def testGenerateMinimalKML(self):
    polygon = model.Polygon(outer_points=[db.GeoPt(1, 2)])
    polygon.put()
    tree = ElementTree.fromstring(polygon.GenerateKML())

    self.assertEqual([i.tag for i in tree.getchildren()], ['outerBoundaryIs'])
    self.assertEqual(tree.find('outerBoundaryIs/LinearRing/coordinates').text,
                     '2.0,1.0 2.0,1.0')


class LineStringKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    points = [db.GeoPt(3.1, 4.2), db.GeoPt(6.1, 7.2)]
    line_string = model.LineString(points=points, altitudes=[8.9, 0.1],
                                   extrude=True, tessellate=False,
                                   altitude_mode='absolute')
    line_string.put()
    tree = ElementTree.fromstring(line_string.GenerateKML())

    self.assertEqual(tree.tag, 'LineString')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['extrude', 'tessellate', 'altitudeMode', 'coordinates'])
    self.assertEqual(tree.find('extrude').text, '1')
    self.assertEqual(tree.find('tessellate').text, '0')
    self.assertEqual(tree.find('altitudeMode').text, 'absolute')
    self.assertEqual(tree.find('coordinates').text, '4.2,3.1,8.9 7.2,6.1,0.1')

  def testGenerateMinimalKML(self):
    line_string = model.LineString(points=[db.GeoPt(3.1, 4.2)])
    line_string.put()
    tree = ElementTree.fromstring(line_string.GenerateKML())

    self.assertEqual([i.tag for i in tree.getchildren()], ['coordinates'])
    self.assertEqual(tree.find('coordinates').text, '4.2,3.1')


class ModelKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    resource1 = model.Resource(layer=layer, filename='c', type='image',
                               external_url='c')
    resource1.put()
    resource2 = model.Resource(layer=layer, filename='d', type='image',
                               external_url='d')
    resource2.put()
    model_resource = model.Resource(layer=layer, filename='e', type='model',
                                    external_url='e')
    model_resource.put()
    alias_targets = [resource1.key().id(), resource2.key().id()]
    model_object = model.Model(model=model_resource,
                               location=db.GeoPt(3.11, 4.22), altitude=5.1,
                               altitude_mode='absolute', heading=1.1, tilt=2.2,
                               roll=3.3, scale_x=4.4, scale_y=5.5, scale_z=6.6,
                               resource_alias_sources=['a', 'b'],
                               resource_alias_targets=alias_targets)
    model_object.put()
    tree = ElementTree.fromstring(model_object.GenerateKML())

    self.assertEqual(tree.tag, 'Model')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['altitudeMode', 'Location', 'Orientation', 'Scale',
                      'Link', 'ResourceMap'])
    self.assertEqual(tree.find('altitudeMode').text, 'absolute')
    self.assertEqual(tree.find('Location/latitude').text, '3.11')
    self.assertEqual(tree.find('Location/longitude').text, '4.22')
    self.assertEqual(tree.find('Location/altitude').text, '5.1')
    self.assertEqual(tree.find('Orientation/heading').text, '1.1')
    self.assertEqual(tree.find('Orientation/tilt').text, '2.2')
    self.assertEqual(tree.find('Orientation/roll').text, '3.3')
    self.assertEqual(tree.find('Scale/x').text, '4.4')
    self.assertEqual(tree.find('Scale/y').text, '5.5')
    self.assertEqual(tree.find('Link/href').text, model_resource.GetURL())
    sources = [i.text for i in tree.findall('ResourceMap/Alias/sourceHref')]
    self.assertEqual(sources, ['a', 'b'])
    targets = [i.text for i in tree.findall('ResourceMap/Alias/targetHref')]
    self.assertEqual(targets, [resource1.GetURL(), resource2.GetURL()])

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, filename='e', type='model',
                              external_url='c')
    resource.put()
    model_object = model.Model(location=db.GeoPt(3.1, 4.2), model=resource)
    model_object.put()
    tree = ElementTree.fromstring(model_object.GenerateKML())

    self.assertEqual([i.tag for i in tree.getchildren()], ['Location', 'Link'])
    self.assertEqual(tree.find('Location/latitude').text, '3.1')
    self.assertEqual(tree.find('Location/longitude').text, '4.2')
    self.assertEqual(tree.find('Link/href').text, resource.GetURL())


class GroundOverlayKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, filename='d', type='image',
                              external_url='d')
    resource.put()
    overlay = model.GroundOverlay(north=1.0, south=2.0, east=3.0, west=4.0,
                                  altitude=4.5, image=resource,
                                  color='AAFFBBCC', draw_order=12,
                                  altitude_mode='relativeToGround')
    overlay.put()
    kml = overlay.GenerateKML(123, '<Dummy />')
    tree = ElementTree.fromstring(kml)

    self.assertEqual(tree.tag, 'GroundOverlay')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['Dummy', 'color', 'drawOrder', 'Icon', 'altitude',
                      'altitudeMode', 'LatLonBox'])
    self.assertEqual(tree.get('id'), 'id123')
    self.assertEqual(tree.find('Dummy').text, None)
    self.assertEqual(tree.find('color').text, 'AAFFBBCC')
    self.assertEqual(tree.find('drawOrder').text, '12')
    self.assertEqual(tree.find('Icon/href').text, resource.GetURL())
    self.assertEqual(tree.find('altitude').text, '4.5')
    self.assertEqual(tree.find('altitudeMode').text, 'relativeToGround')
    self.assertEqual(tree.find('LatLonBox/north').text, '1.0')
    self.assertEqual(tree.find('LatLonBox/south').text, '2.0')
    self.assertEqual(tree.find('LatLonBox/east').text, '3.0')
    self.assertEqual(tree.find('LatLonBox/west').text, '4.0')

  def testGenerateMinimalUniformKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, filename='d', type='image',
                              external_url='d')
    resource.put()
    overlay = model.GroundOverlay(north=1.0, south=2.0, east=3.0, west=4.0,
                                  image=resource)
    overlay.put()
    kml = overlay.GenerateKML(123, '<Dummy />')
    tree = ElementTree.fromstring(kml)

    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['Dummy', 'Icon', 'LatLonBox'])
    self.assertEqual(tree.find('Dummy').text, None)
    self.assertEqual(tree.find('Icon/href').text, resource.GetURL())
    self.assertEqual(tree.find('LatLonBox/north').text, '1.0')
    self.assertEqual(tree.find('LatLonBox/south').text, '2.0')
    self.assertEqual(tree.find('LatLonBox/east').text, '3.0')
    self.assertEqual(tree.find('LatLonBox/west').text, '4.0')

  def testGenerateMinimalNonUniformKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, filename='d', type='image',
                              external_url='d')
    resource.put()
    overlay = model.GroundOverlay(image=resource, is_quad=True,
                                  corners=[db.GeoPt(-1, -3), db.GeoPt(-1, 1),
                                           db.GeoPt(2, 1), db.GeoPt(4, -2)])
    overlay.put()
    kml = overlay.GenerateKML(123, '<Dummy />')
    # Can't easily register namespace; fake it.
    kml = kml.replace('gx:LatLonQuad', 'gx_LatLonQuad')
    tree = ElementTree.fromstring(kml)

    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['Dummy', 'Icon', 'gx_LatLonQuad'])
    self.assertEqual(tree.find('Dummy').text, None)
    self.assertEqual(tree.find('Icon/href').text, resource.GetURL())
    self.assertEqual(tree.find('gx_LatLonQuad/coordinates').text,
                     '-3.0,-1.0 1.0,-1.0 1.0,2.0 -2.0,4.0')


class PhotoOverlayKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, filename='d', type='image',
                              external_url='d')
    resource.put()
    overlay = model.PhotoOverlay(location=db.GeoPt(6, 7), color='AAEE77CC',
                                 image=resource, draw_order=88, altitude=4.5,
                                 rotation=6.7, shape='cylinder', view_left=4.5,
                                 view_right=67.8, view_top=90.1,
                                 view_bottom=23.4, view_near=56.7,
                                 pyramid_height=78, pyramid_width=89,
                                 pyramid_tile_size=901,
                                 pyramid_grid_origin='lowerLeft')
    overlay.put()
    tree = ElementTree.fromstring(overlay.GenerateKML(123, '<Dummy />'))

    self.assertEqual(tree.tag, 'PhotoOverlay')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['Dummy', 'color', 'drawOrder', 'Icon', 'rotation',
                      'ViewVolume', 'Point', 'shape', 'ImagePyramid'])
    self.assertEqual(tree.get('id'), 'id123')
    self.assertEqual(tree.find('Dummy').text, None)
    self.assertEqual(tree.find('color').text, 'AAEE77CC')
    self.assertEqual(tree.find('drawOrder').text, '88')
    self.assertEqual(tree.find('Icon/href').text, resource.GetURL())
    self.assertEqual(tree.find('rotation').text, '6.7')
    self.assertEqual(tree.find('ViewVolume/leftFov').text, '4.5')
    self.assertEqual(tree.find('ViewVolume/rightFov').text, '67.8')
    self.assertEqual(tree.find('ViewVolume/topFov').text, '90.1')
    self.assertEqual(tree.find('ViewVolume/bottomFov').text, '23.4')
    self.assertEqual(tree.find('ViewVolume/near').text, '56.7')
    self.assertEqual(tree.find('Point/coordinates').text, '7.0,6.0,4.5')
    self.assertEqual(tree.find('shape').text, 'cylinder')
    self.assertEqual(tree.find('ImagePyramid/maxHeight').text, '78')
    self.assertEqual(tree.find('ImagePyramid/maxWidth').text, '89')
    self.assertEqual(tree.find('ImagePyramid/tileSize').text, '901')
    self.assertEqual(tree.find('ImagePyramid/gridOrigin').text, 'lowerLeft')

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, filename='d', type='image',
                              external_url='d')
    resource.put()
    overlay = model.PhotoOverlay(location=db.GeoPt(6, 7), shape='rectangle',
                                 image=resource, view_left=4.5, view_right=67.8,
                                 view_top=90.1, view_bottom=23.4, view_near=56.)
    overlay.put()
    tree = ElementTree.fromstring(overlay.GenerateKML(123, '<Dummy />'))

    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['Dummy', 'Icon', 'ViewVolume', 'Point'])
    self.assertEqual(tree.find('Dummy').text, None)
    self.assertEqual(tree.find('Icon/href').text, resource.GetURL())
    self.assertEqual(tree.find('ViewVolume/leftFov').text, '4.5')
    self.assertEqual(tree.find('ViewVolume/rightFov').text, '67.8')
    self.assertEqual(tree.find('ViewVolume/topFov').text, '90.1')
    self.assertEqual(tree.find('ViewVolume/bottomFov').text, '23.4')
    self.assertEqual(tree.find('ViewVolume/near').text, '56.0')
    self.assertEqual(tree.find('Point/coordinates').text, '7.0,6.0,0')


class RegionKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    region = model.Region(layer=layer, name='a', north=0.1, south=0.2, east=0.3,
                          west=0.4, min_altitude=5.6, max_altitude=6.7,
                          altitude_mode='absolute', lod_min=8, lod_max=9,
                          lod_fade_min=2, lod_fade_max=4)
    region.put()
    tree = ElementTree.fromstring(region.GenerateKML())

    self.assertEqual(tree.tag, 'Region')
    self.assertEqual(tree.get('id'), 'id%d' % region.key().id())
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['LatLonAltBox', 'Lod'])
    self.assertEqual(tree.find('LatLonAltBox/north').text, '0.1')
    self.assertEqual(tree.find('LatLonAltBox/south').text, '0.2')
    self.assertEqual(tree.find('LatLonAltBox/east').text, '0.3')
    self.assertEqual(tree.find('LatLonAltBox/west').text, '0.4')
    self.assertEqual(tree.find('LatLonAltBox/minAltitude').text, '5.6')
    self.assertEqual(tree.find('LatLonAltBox/maxAltitude').text, '6.7')
    self.assertEqual(tree.find('LatLonAltBox/altitudeMode').text, 'absolute')
    self.assertEqual(tree.find('Lod/minLodPixels').text, '8')
    self.assertEqual(tree.find('Lod/maxLodPixels').text, '9')
    self.assertEqual(tree.find('Lod/minFadeExtent').text, '2')
    self.assertEqual(tree.find('Lod/maxFadeExtent').text, '4')

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    region = model.Region(layer=layer, north=0.1, south=0.2, east=0.3, west=0.4)
    region.put()
    tree = ElementTree.fromstring(region.GenerateKML())

    self.assertEqual([i.tag for i in tree.getchildren()], ['LatLonAltBox'])
    self.assertEqual([i.tag for i in tree.find('LatLonAltBox').getchildren()],
                     ['north', 'south', 'east', 'west'])
    self.assertEqual(tree.find('LatLonAltBox/north').text, '0.1')
    self.assertEqual(tree.find('LatLonAltBox/south').text, '0.2')
    self.assertEqual(tree.find('LatLonAltBox/east').text, '0.3')
    self.assertEqual(tree.find('LatLonAltBox/west').text, '0.4')


class LinkKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    region = model.Region(layer=layer, north=0.1, south=0.2, east=0.3, west=0.4)
    region.put()
    resource = model.Resource(layer=layer, filename='d', type='icon',
                              external_url='d')
    resource.put()
    link = model.Link(layer=layer, url='a', name='b', region=region,
                      icon=resource, item_type='radioFolder', description='def',
                      custom_kml='<dummy>Hello</dummy>')
    link.put()
    tree = ElementTree.fromstring(link.GenerateKML())

    self.assertEqual(tree.tag, 'NetworkLink')
    self.assertEqual(tree.get('id'), 'id%d' % link.key().id())
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['name', 'Style', 'Region', 'Link', 'dummy'])
    self.assertEqual(tree.find('name').text, 'b')
    self.assertEqual(tree.find('Style/ListStyle/ItemIcon/href').text,
                     resource.GetURL())
    self.assertEqual(tree.find('Style/ListStyle/listItemType').text,
                     'radioFolder')
    self.assertEqual(tree.find('Style/BalloonStyle/text').text, 'def')
    self.assertEqual(tree.find('Link/href').text, 'a')
    self.assertEqual(tree.find('dummy').text, 'Hello')

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    link = model.Link(layer=layer, url='a', name='b')
    link.put()
    tree = ElementTree.fromstring(link.GenerateKML())

    self.assertEqual([i.tag for i in tree.getchildren()], ['name', 'Link'])
    self.assertEqual(tree.find('name').text, 'b')
    self.assertEqual(tree.find('Link/href').text, 'a')


class StyleKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    icon = model.Resource(layer=layer, filename='d', type='icon',
                          external_url='d')
    icon.put()
    highlight_icon = model.Resource(layer=layer, filename='e', type='icon',
                                    external_url='e')
    highlight_icon.put()
    style = model.Style(layer=layer, has_highlight=True, name='def',
                        icon=icon, icon_color='AAEE77CC', icon_scale=1.5,
                        icon_heading=34.5, label_color='CCDD7654',
                        label_scale=2.3, balloon_color='7FD5E382',
                        text_color='82957100', line_color='22551276',
                        line_width=81, polygon_color='900df00d',
                        polygon_fill=False, polygon_outline=True,
                        highlight_icon=highlight_icon,
                        highlight_icon_color='DEADBEEF',
                        highlight_icon_scale=8.7, highlight_icon_heading=6.5,
                        highlight_label_color='D000000D',
                        highlight_label_scale=2.2,
                        highlight_balloon_color='73577357',
                        highlight_text_color='C01DB007',
                        highlight_line_color='ADEADBA7',
                        highlight_line_width=56,
                        highlight_polygon_color='baddf00d',
                        highlight_polygon_fill=True,
                        highlight_polygon_outline=False)
    style.put()
    kml = style.GenerateKML()
    # Must have a single root element.
    tree = ElementTree.fromstring('<dummy>%s</dummy>' % kml)

    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['Style', 'Style', 'StyleMap'])
    normal, highlight, style_map = tree.getchildren()

    self.assertEqual(style_map.get('id'), 'id%d' % style.key().id())
    self.assertEqual([i.tag for i in style_map.getchildren()], ['Pair', 'Pair'])
    normal_pair = style_map.getchildren()[0]
    self.assertEqual(normal_pair.find('key').text, 'normal')
    self.assertEqual(normal_pair.find('styleUrl').text, '#' + normal.get('id'))
    highlight_pair = style_map.getchildren()[1]
    self.assertEqual(highlight_pair.find('key').text, 'highlight')
    self.assertEqual(highlight_pair.find('styleUrl').text,
                     '#' + highlight.get('id'))

    self.assertEqual([i.tag for i in normal.getchildren()],
                     ['IconStyle', 'BalloonStyle', 'LabelStyle', 'LineStyle',
                      'PolyStyle', 'ListStyle'])
    self.assertEqual(normal.find('IconStyle/Icon/href').text, icon.GetURL())
    self.assertEqual(normal.find('IconStyle/color').text, 'AAEE77CC')
    self.assertEqual(normal.find('IconStyle/scale').text, '1.5')
    self.assertEqual(normal.find('IconStyle/heading').text, '34.5')
    self.assertEqual(normal.find('BalloonStyle/bgColor').text, '7FD5E382')
    self.assertEqual(normal.find('BalloonStyle/textColor').text, '82957100')
    self.assertEqual(normal.find('LabelStyle/color').text, 'CCDD7654')
    self.assertEqual(normal.find('LabelStyle/scale').text, '2.3')
    self.assertEqual(normal.find('LineStyle/color').text, '22551276')
    self.assertEqual(normal.find('LineStyle/width').text, '81')
    self.assertEqual(normal.find('PolyStyle/color').text, '900df00d')
    self.assertEqual(normal.find('PolyStyle/fill').text, '0')
    self.assertEqual(normal.find('PolyStyle/outline').text, '1')
    self.assertEqual(normal.find('ListStyle/ItemIcon/href').text, icon.GetURL())

    self.assertEqual([i.tag for i in highlight.getchildren()],
                     ['IconStyle', 'BalloonStyle', 'LabelStyle', 'LineStyle',
                      'PolyStyle', 'ListStyle'])
    self.assertEqual(highlight.find('IconStyle/Icon/href').text,
                     highlight_icon.GetURL())
    self.assertEqual(highlight.find('IconStyle/color').text, 'DEADBEEF')
    self.assertEqual(highlight.find('IconStyle/scale').text, '8.7')
    self.assertEqual(highlight.find('IconStyle/heading').text, '6.5')
    self.assertEqual(highlight.find('BalloonStyle/bgColor').text, '73577357')
    self.assertEqual(highlight.find('BalloonStyle/textColor').text, 'C01DB007')
    self.assertEqual(highlight.find('LabelStyle/color').text, 'D000000D')
    self.assertEqual(highlight.find('LabelStyle/scale').text, '2.2')
    self.assertEqual(highlight.find('LineStyle/color').text, 'ADEADBA7')
    self.assertEqual(highlight.find('LineStyle/width').text, '56')
    self.assertEqual(highlight.find('PolyStyle/color').text, 'baddf00d')
    self.assertEqual(highlight.find('PolyStyle/fill').text, '1')
    self.assertEqual(highlight.find('PolyStyle/outline').text, '0')
    self.assertEqual(highlight.find('ListStyle/ItemIcon/href').text,
                     highlight_icon.GetURL())

  def testGeneratePartialKML(self):
    layer = model.Layer(name='abc', world='earth', dynamic_balloons=True)
    layer.put()
    style = model.Style(layer=layer, has_highlight=False, name='def',
                        icon_color='AAEE77CC', label_color='CCDD7654',
                        text_color='82957100', line_width=81, polygon_fill=True)
    style.put()
    tree = ElementTree.fromstring(style.GenerateKML())

    self.assertEqual(tree.tag, 'Style')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['IconStyle', 'BalloonStyle', 'LabelStyle', 'LineStyle',
                      'PolyStyle'])
    self.assertEqual([i.tag for i in tree.find('IconStyle').getchildren()],
                     ['color'])
    self.assertEqual(tree.find('IconStyle/color').text, 'AAEE77CC')
    self.assertEqual([i.tag for i in tree.find('BalloonStyle').getchildren()],
                     ['textColor', 'text'])
    self.assertEqual(tree.find('BalloonStyle/textColor').text, '82957100')
    self.assertTrue(settings.BALLOON_LINK_PLACEHOLDER in
                    tree.find('BalloonStyle/text').text)
    self.assertEqual([i.tag for i in tree.find('LabelStyle').getchildren()],
                     ['color'])
    self.assertEqual(tree.find('LabelStyle/color').text, 'CCDD7654')
    self.assertEqual([i.tag for i in tree.find('LineStyle').getchildren()],
                     ['width'])
    self.assertEqual(tree.find('LineStyle/width').text, '81')
    self.assertEqual([i.tag for i in tree.find('PolyStyle').getchildren()],
                     ['fill'])
    self.assertEqual(tree.find('PolyStyle/fill').text, '1')

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='abc', world='earth')
    layer.put()
    style = model.Style(layer=layer, name='def')
    style.put()
    tree = ElementTree.fromstring(style.GenerateKML())

    self.assertEqual(tree.tag, 'Style')
    self.assertEqual([i.tag for i in tree.getchildren()], ['BalloonStyle'])
    self.assertEqual([i.tag for i in tree.find('BalloonStyle').getchildren()],
                     ['text'])


class EntityKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteSinglePlacemarkKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    schema = model.Schema(layer=layer, name='b')
    schema.put()
    template_text = ('x {{f1}} y')
    template = model.Template(schema=schema, name='c', text=template_text)
    template.put()
    model.Field(schema=schema, name='f1', type='text').put()
    model.Field(schema=schema, name='f2', type='integer').put()
    style = model.Style(layer=layer, name='d')
    style.put()
    region = model.Region(layer=layer, north=0.1, south=0.2, east=0.3, west=0.4)
    region.put()
    entity = model.Entity(layer=layer, name='e', snippet='f', template=template,
                          style=style, region=region, field_f1='ab', field_f2=3,
                          folder_index=5, view_location=db.GeoPt(6, 7),
                          view_altitude=1.2, view_heading=3.4, view_tilt=5.6,
                          view_range=7.8)
    entity.put()
    point = model.Point(location=db.GeoPt(1, 2), parent=entity)
    point_id = point.put().id()
    entity.geometries = [point_id]
    entity.put()

    tree = ElementTree.fromstring(entity.GenerateKML())

    self.assertEqual(tree.tag, 'Placemark')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['name', 'Snippet', 'description', 'styleUrl', 'LookAt',
                      'Region', 'Point'])
    self.assertEqual(tree.get('id'), 'id%d' % entity.key().id())
    self.assertEqual(tree.find('name').text, 'e')
    self.assertEqual(tree.find('Snippet').text, 'f')
    self.assertEqual(tree.find('description').text, template.Evaluate(entity))
    self.assertEqual(tree.find('styleUrl').text,
                     'root.kml#id%d' % style.key().id())
    self.assertEqual(tree.find('LookAt/longitude').text, '7.0')
    self.assertEqual(tree.find('LookAt/latitude').text, '6.0')
    self.assertEqual(tree.find('LookAt/altitude').text, '1.2')
    self.assertEqual(tree.find('LookAt/heading').text, '3.4')
    self.assertEqual(tree.find('LookAt/tilt').text, '5.6')
    self.assertEqual(tree.find('LookAt/range').text, '7.8')

  def testGenerateCameraViewKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    entity = model.Entity(layer=layer, name='b', view_location=db.GeoPt(6, 7),
                          view_altitude=1.2, view_heading=3.4, view_tilt=5.6,
                          view_roll=7.8, view_is_camera=True)
    entity.put()
    point = model.Point(location=db.GeoPt(1, 2), parent=entity)
    point_id = point.put().id()
    entity.geometries = [point_id]
    entity.put()

    tree = ElementTree.fromstring(entity.GenerateKML())

    self.assertEqual(tree.tag, 'Placemark')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['name', 'Snippet', 'Camera', 'Point'])
    self.assertEqual(tree.find('name').text, 'b')
    self.assertEqual(tree.find('Camera/longitude').text, '7.0')
    self.assertEqual(tree.find('Camera/latitude').text, '6.0')
    self.assertEqual(tree.find('Camera/altitude').text, '1.2')
    self.assertEqual(tree.find('Camera/heading').text, '3.4')
    self.assertEqual(tree.find('Camera/tilt').text, '5.6')
    self.assertEqual(tree.find('Camera/roll').text, '7.8')

  def testGenerateMinimalOverlayKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    resource = model.Resource(layer=layer, filename='d', type='icon',
                              external_url='d')
    resource.put()
    entity = model.Entity(layer=layer, name='b')
    entity.put()
    overlay = model.PhotoOverlay(image=resource, shape='sphere', view_near=56.7,
                                 view_right=67.8, view_top=90.1, view_left=4.5,
                                 view_bottom=23.4, location=db.GeoPt(1, 2),
                                 parent=entity)
    overlay_id = overlay.put().id()
    entity.geometries = [overlay_id]
    entity.put()

    tree = ElementTree.fromstring(entity.GenerateKML())

    self.assertEqual(tree.tag, 'PhotoOverlay')
    self.assertEqual([i.tag for i in tree.getchildren()][:2],
                     ['name', 'Snippet'])
    self.assertEqual(tree.find('name').text, 'b')

  def testGenerateMultiGeometryKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    entity = model.Entity(layer=layer, name='b')
    entity.put()
    point = model.Point(location=db.GeoPt(1.11, 2.22), parent=entity)
    point_id = point.put().id()
    polygon = model.Polygon(outer_points=[db.GeoPt(1, 2)], parent=entity)
    polygon_id = polygon.put().id()
    entity.geometries = [point_id, polygon_id]
    entity.put()
    tree = ElementTree.fromstring(entity.GenerateKML())

    self.assertEqual(tree.tag, 'Placemark')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['name', 'Snippet', 'MultiGeometry'])
    self.assertEqual(tree.get('id'), 'id%d' % entity.key().id())
    self.assertEqual(tree.find('name').text, 'b')
    self.assertEqual([i.tag for i in tree.find('MultiGeometry').getchildren()],
                     ['Point', 'Polygon'])

  def testGenerateOverlaysAndMultiGeometryKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    entity = model.Entity(layer=layer, name='b')
    entity.put()
    point = model.Point(location=db.GeoPt(1.11, 2.22), parent=entity)
    point.put()
    polygon = model.Polygon(outer_points=[db.GeoPt(1, 2)], parent=entity)
    polygon.put()
    resource = model.Resource(layer=layer, filename='d', type='image',
                              external_url='d')
    resource.put()
    overlay = model.GroundOverlay(north=1.0, south=2.0, east=3.0, west=4.0,
                                  image=resource, parent=entity)
    overlay.put()
    entity.geometries = [i.key().id() for i in (point, polygon, overlay)]
    entity.put()

    tree = ElementTree.fromstring('<dummy>%s</dummy>' % entity.GenerateKML())

    self.assertEqual(tree.tag, 'dummy')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['Placemark', 'GroundOverlay'])
    self.assertEqual(tree.find('Placemark').get('id'),
                     'id%d' % entity.key().id())
    self.assertEqual(tree.find('GroundOverlay').get('id'),
                     'id%d_%d' % (entity.key().id(), 0))


class FolderKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    region = model.Region(layer=layer, north=0.1, south=0.2, east=0.3, west=0.4)
    region.put()
    resource = model.Resource(layer=layer, filename='d', type='icon',
                              external_url='d')
    resource.put()
    folder = model.Folder(layer=layer, name='F', icon=resource, region=region,
                          item_type='radioFolder', description='def',
                          custom_kml='<dummy>Hello</dummy>')
    folder.put()
    subfolder = model.Folder(layer=layer, name='G', folder=folder,
                             folder_index=1)
    subfolder.put()

    entity_spec = (('a', folder, 2), ('b', folder, 0),
                   ('c', subfolder, 3), ('d', subfolder, 4))
    for name, entity_folder, folder_index in entity_spec:
      entity = model.Entity(layer=layer, name=name, folder=entity_folder,
                            folder_index=folder_index)
      entity.put()
      point_id = model.Point(location=db.GeoPt(1, 2), parent=entity).put().id()
      entity.geometries = [point_id]
      entity.put()

    tree = ElementTree.fromstring(folder.GenerateKML())

    self.assertEqual(tree.tag, 'Folder')
    self.assertEqual([i.tag for i in tree.getchildren()],
                     ['name', 'Style', 'Region', 'Placemark', 'Folder',
                      'Placemark', 'dummy'])
    self.assertEqual(tree.get('id'), 'id%d' % folder.key().id())
    self.assertEqual(tree.find('name').text, 'F')
    self.assertEqual(tree.find('Style/ListStyle/ItemIcon/href').text,
                     resource.GetURL())
    self.assertEqual(tree.find('Style/ListStyle/listItemType').text,
                     'radioFolder')
    self.assertEqual(tree.find('Style/BalloonStyle/text').text, 'def')
    self.assertEqual(tree.find('dummy').text, 'Hello')

    entity1, subfolder, entity2 = tree.getchildren()[3:-1]
    self.assertEqual([i.tag for i in subfolder.getchildren()],
                     ['name', 'Placemark', 'Placemark'])
    self.assertEqual(subfolder.find('name').text, 'G')
    subentity1, subentity2 = subfolder.getchildren()[1:]

    self.assertEqual(entity1.find('name').text, 'b')
    self.assertEqual(entity2.find('name').text, 'a')
    self.assertEqual(subentity1.find('name').text, 'c')
    self.assertEqual(subentity2.find('name').text, 'd')

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    folder = model.Folder(layer=layer, name='F')
    folder.put()
    tree = ElementTree.fromstring(folder.GenerateKML())

    self.assertEqual(tree.tag, 'Folder')
    self.assertEqual([i.tag for i in tree.getchildren()], ['name'])
    self.assertEqual(tree.find('name').text, 'F')


class LayerKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='a', description='bc', world='mars',
                        custom_kml='<address>dummy</address>',
                        item_type='radioFolder')
    layer.put()
    resource = model.Resource(layer=layer, filename='d', type='icon',
                              external_url='d')
    resource.put()
    layer.icon = resource
    layer.put()
    folder = model.Folder(layer=layer, name='F', folder_index=1)
    folder.put()
    entity_spec = (('j', None, 0), ('k', None, 1), ('l', folder, None))
    for name, folder, folder_index in entity_spec:
      entity = model.Entity(layer=layer, name=name, folder=folder,
                            folder_index=folder_index)
      entity.put()
      point_id = model.Point(location=db.GeoPt(1, 2), parent=entity).put().id()
      entity.geometries = [point_id]
      entity.put()
    style1_key = model.Style(layer=layer, name='def').put()
    style2_key = model.Style(layer=layer, name='ghi').put()

    kml = _GetRidOfNamespace(layer.GenerateKML())
    tree = ElementTree.fromstring(kml)

    self.assertEqual(tree.tag, 'kml')
    self.assertEqual([i.tag for i in tree.getchildren()], ['Document'])
    self.assertEqual(tree.get('hint'), 'target=mars')

    document = tree.find('Document')
    self.assertEqual([i.tag for i in document.getchildren()],
                     ['name', 'address', 'Style', 'Style', 'Style',
                      'Placemark', 'Placemark', 'Folder'])
    self.assertEqual(document.get('id'), None)
    self.assertEqual(document.find('name').text, 'a')
    self.assertEqual(document.find('address').text, 'dummy')

    layer_style, style1, style2 = document.findall('Style')
    self.assertEqual(layer_style.get('id'), None)
    self.assertEqual(set([style1.get('id'), style2.get('id')]),
                     set(['id%d' % style1_key.id(), 'id%d' % style2_key.id()]))

    self.assertEqual(layer_style.find('ListStyle/ItemIcon/href').text,
                     resource.GetURL())
    self.assertEqual(layer_style.find('ListStyle/listItemType').text,
                     'radioFolder')
    self.assertEqual(layer_style.find('BalloonStyle/text').text, 'bc')

    self.assertEqual(document.find('Folder/name').text, 'F')
    entity1, entity2 = document.findall('Placemark')
    self.assertEqual(entity1.find('name').text, 'j')
    self.assertEqual(entity2.find('name').text, 'k')

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    kml = _GetRidOfNamespace(layer.GenerateKML())
    tree = ElementTree.fromstring(kml)

    self.assertEqual(tree.tag, 'kml')
    self.assertEqual([i.tag for i in tree.getchildren()], ['Document'])
    self.assertEqual([i.tag for i in tree.find('Document').getchildren()],
                     ['name'])
    self.assertEqual(tree.find('Document/name').text, 'a')

  def testGenerateRegionatedKML(self):
    layer = model.Layer(name='a', world='mars', auto_managed=True, baked=True)
    layer.put()
    entity_ids = []
    for name, baked in (('b', True), ('c', True), ('d', None)):
      entity = model.Entity(layer=layer, name=name, baked=baked)
      entity_id = entity.put().id()
      point_id = model.Point(location=db.GeoPt(1, 2), parent=entity).put().id()
      entity.geometries = [point_id]
      entity.put()
      entity_ids.append(entity_id)
    model.Style(layer=layer, name='e').put()
    division = model.Division(layer=layer, south=0.1, north=2.3, west=4.5,
                              east=6.7, entities=[entity_ids[0]], baked=True)
    division.put()
    model.Division(layer=layer, south=0.1, north=2.3, west=4.5, east=6.7,
                   entities=[entity_ids[1]], baked=True,
                   parent_division=division).put()

    kml = _GetRidOfNamespace(layer.GenerateKML())
    tree = ElementTree.fromstring(kml)

    self.assertEqual(tree.tag, 'kml')
    self.assertEqual([i.tag for i in tree.getchildren()], ['Document'])
    document = tree.find('Document')
    self.assertEqual([i.tag for i in document.getchildren()],
                     ['name', 'Style', 'Placemark', 'NetworkLink', 'Placemark'])
    placemarks = document.findall('Placemark')
    self.assertEqual(placemarks[0].get('id'), 'id%d' % entity_ids[0])
    self.assertEqual(placemarks[1].get('id'), 'id%d' % entity_ids[2])

  def testKMLGenerationFailures(self):
    layer = model.Layer(name='abc', world='earth')
    self.assertRaises(db.NotSavedError, layer.GenerateKML)
    layer.auto_managed = True
    layer.baked = False
    layer.put()
    self.assertRaises(model.KMLGenerationError, layer.GenerateKML)


class DivisionKMLGenerationTest(unittest.TestCase):

  def testGenerateCompleteKML(self):
    layer = model.Layer(name='a', world='earth', division_lod_min=123,
                        division_lod_max=456, division_lod_min_fade=789,
                        division_lod_max_fade=231)
    layer.put()
    entities = []
    for _ in xrange(3):
      entity = model.Entity(layer=layer, name='b')
      entity_id = entity.put().id()
      point_id = model.Point(location=db.GeoPt(1, 2), parent=entity).put().id()
      entity.geometries = [point_id]
      entity.put()
      entities.append(entity_id)
    division = model.Division(layer=layer, south=0.1, north=2.3, west=4.5,
                              east=6.7, baked=True, entities=entities)
    division.put()
    subdivison_id = model.Division(layer=layer, south=1.0, north=2.0, west=5.0,
                                   east=6.0, baked=True,
                                   parent_division=division).put().id()

    kml = _GetRidOfNamespace(division.GenerateKML())
    tree = ElementTree.fromstring(kml)

    self.assertEqual(tree.tag, 'kml')
    self.assertEqual(tree.get('hint'), None)
    document = tree.find('Document')
    self.assertEqual(document.get('id'), None)
    self.assertEqual([i.tag for i in document.getchildren()],
                     ['Placemark'] * 3 + ['NetworkLink', 'Region'])

    link = document.find('NetworkLink')
    self.assertEqual([i.tag for i in link.getchildren()], ['Link', 'Region'])
    self.assertEqual(link.find('Link/href').text, 'k%d.kml' % subdivison_id)
    self.assertEqual(link.find('Link/viewRefreshMode').text, 'onRegion')
    self.assertEqual(link.find('Link/viewRefreshMode').text, 'onRegion')

    self.assertEqual(link.find('Region/LatLonAltBox/south').text, '1.0')
    self.assertEqual(link.find('Region/LatLonAltBox/north').text, '2.0')
    self.assertEqual(link.find('Region/LatLonAltBox/west').text, '5.0')
    self.assertEqual(link.find('Region/LatLonAltBox/east').text, '6.0')
    self.assertEqual(link.find('Region/Lod/minLodPixels').text, '123')
    self.assertEqual(link.find('Region/Lod/maxLodPixels').text, '456')

    self.assertEqual(document.find('Region/LatLonAltBox/south').text, '0.1')
    self.assertEqual(document.find('Region/LatLonAltBox/north').text, '2.3')
    self.assertEqual(document.find('Region/LatLonAltBox/west').text, '4.5')
    self.assertEqual(document.find('Region/LatLonAltBox/east').text, '6.7')
    self.assertEqual(document.find('Region/Lod/minLodPixels').text, '123')
    self.assertEqual(document.find('Region/Lod/minFadeExtent').text, '789')
    self.assertEqual(document.find('Region/Lod/maxLodPixels').text, '456')
    self.assertEqual(document.find('Region/Lod/maxFadeExtent').text, '231')

  def testGenerateMinimalKML(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    division = model.Division(layer=layer, south=0.1, north=2.3, west=4.5,
                              east=6.7, baked=True)
    division.put()
    kml = _GetRidOfNamespace(division.GenerateKML())
    document = ElementTree.fromstring(kml).find('Document')

    self.assertEqual(document.get('id'), None)
    self.assertEqual([i.tag for i in document.getchildren()], ['Region'])
    self.assertEqual(document.find('Region/LatLonAltBox/south').text, '0.1')
    self.assertEqual(document.find('Region/LatLonAltBox/north').text, '2.3')
    self.assertEqual(document.find('Region/LatLonAltBox/west').text, '4.5')
    self.assertEqual(document.find('Region/LatLonAltBox/east').text, '6.7')
    self.assertEqual(document.find('Region/Lod/minLodPixels').text, '512')
    self.assertEqual(document.find('Region/Lod/minFadeExtent').text, '128')
    self.assertEqual(document.find('Region/Lod/maxLodPixels').text, '-1')
    self.assertEqual(document.find('Region/Lod/maxFadeExtent').text, '128')

  def testUnbakedKMLGenerationFailure(self):
    layer = model.Layer(name='a', world='earth')
    layer.put()
    division = model.Division(layer=layer, south=0.1, north=2.3, west=4.5,
                              east=6.7, baked=False)
    self.assertRaises(model.KMLGenerationError, division.GenerateKML)
