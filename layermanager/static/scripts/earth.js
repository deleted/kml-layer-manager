// Copyright 2010 Google Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

/**
 * @fileoverview An embeddable Earth API-based geometry editing control.
 */

google.load('earth', '1');

/** The main Earth editor namespace. */
layermanager.earth = {};
/** A namespace for variables defining the current editor states. */
layermanager.earth.state = {};
/** A namespace for functions and events to be used by clients. */
layermanager.earth.api = {};

/*******************************************************************************
*                             Constants and Enums                              *
*******************************************************************************/

/**
 * The default distance in meters of the camera from the object when centering
 * the camera on an object.
 * @type {number}
 * @const
 */
layermanager.earth.DEFAULT_RANGE = 100000;

/**
 * A multiplier for the rate at which altitude changes when raising or lowering
 * an object.
 * @type {number}
 * @const
 */
layermanager.earth.ALTITUDE_RATE = 0.001;

/**
 * A multiplier for the rate at which rotation changes when rotating an object.
 * @type {number}
 * @const
 */
layermanager.earth.ROTATE_RATE = 0.5;

/**
 * A multiplier for the rate at which scale changes when scaling an object.
 * @type {number}
 * @const
 */
layermanager.earth.SCALE_RATE = 0.00008;

/**
 * The minimum number of milliseconds between two calls to a callback whose
 * call frequency has been limited by limitCallFrequency().
 * @type {number}
 * @const
 */
layermanager.earth.CALLBACK_INTERVAL_LIMIT = 50;

/**
 * The default KML style properties for the object being edited. Must be in a
 * format acceptable by GEarthExtensions.dom.buildStyle().
 * @type {Object}
 * @const
 */
layermanager.earth.DEFAULT_STYLE = {
  icon: {stockIcon: 'paddle/blu-blank', hotSpot: {left: '50%', top: '100%'}},
  label: 'FFFFFFFF',
  line: {width: 4, color: 'FF660000'},
  poly: {fill: true, outline: true, color: '88AA3333'}
};

/**
 * The URL from where a list of resources can be acquired.
 * @type {string}
 * @const
 */
layermanager.earth.RESOURCE_LIST_URL = '/resource-list/';

/**
 * The URL from where a layer's KML representation can be acquired.
 * @type {string}
 * @const
 */
layermanager.earth.LAYER_KML_URL = '/serve/{ID}/root.kml';

/**
 * The URL of the crosshair icon which is used for corners of resizeable
 * regions and ground overlays.
 * @type {string}
 * @const
 */
layermanager.earth.CROSSHAIR_ICON_URL = 'http://' + window.location.host +
                                     '/static/img/crosshair.png';
/**
 * The URL of the icon that is used for the placemark placed over 3D models for
 * picking.
 * @type {string}
 * @const
 */
layermanager.earth.MODEL_ICON_URL = ('http://' + window.location.host +
                                     '/static/img/model_small.png');
/**
 * The URL of the icon that is used for the placemark placed over ground
 * overlays for picking.
 * @type {string}
 * @const
 */
layermanager.earth.OVERLAY_ICON_URL = ('http://' + window.location.host +
                                       '/static/img/layer.png');
/**
 * The URL of the icon that is placed in the corner of the widget's window and
 * acts as a resizing grip. Not used inside the plugin, so relative.
 * @type {string}
 * @const
 */
layermanager.earth.RESIZE_HANDLE_URL = '/static/img/resize_handle.png';

/**
 * A description of the widget used to move the object being edited over the
 * surface of the planet.
 * Contains the following properties:
 *   normal: The URL of the widget's icon.
 *   over: The URL of the icon used for this widget when the cursor is over it.
 *   width: The width of the widget in pixels.
 *   height: The height of the widget in pixels.
 *   x: The signed horizontal offset of the widget in pixels from the
 *     centerpoint of the object being edited.
 *   y: The signed vertical offset of the widget in pixels from the centerpoint
 *     of the object being edited.
 * @type {Object}
 * @const
 */
layermanager.earth.MOVE_WIDGET = {
  normal: 'http://' + window.location.host + '/static/img/move_surface.png',
  over: 'http://' + window.location.host + '/static/img/move_surface_over.png',
  width: 32, height: 12, x: -16, y: 0
};

/**
 * A description of the widget used to move the object being edited up or down.
 * Contains the same properties as layermanager.earth.MOVE_WIDGET.
 * @type {Object}
 * @const
 */
layermanager.earth.ALTITUDE_WIDGET = {
  normal: 'http://' + window.location.host + '/static/img/move_vertical.png',
  over: 'http://' + window.location.host + '/static/img/move_vertical_over.png',
  width: 32, height: 20, x: -16, y: -20
};

/**
 * A description of the widget used to rotate the object being edited.
 * Contains the same properties as layermanager.earth.MOVE_WIDGET.
 * @type {Object}
 * @const
 */
layermanager.earth.ROTATE_WIDGET = {
  normal: 'http://' + window.location.host + '/static/img/rotate.png',
  over: 'http://' + window.location.host + '/static/img/rotate_over.png',
  width: 32, height: 10, x: -16, y: 12
};

/**
 * A description of the widget used to scale the object being edited.
 * Contains the same properties as layermanager.earth.MOVE_WIDGET.
 * @type {Object}
 * @const
 */
layermanager.earth.SCALE_WIDGET = {
  normal: 'http://' + window.location.host + '/static/img/scale.png',
  over: 'http://' + window.location.host + '/static/img/scale_over.png',
  width: 32, height: 14, x: -16, y: -34
};

/**
 * The ratio of the width/height of a default new geometry to the size of the
 * plugin viewport.
 * @type {number}
 * @const
 */
layermanager.earth.DEFAULT_NEW_GEOMETRY_SIZE = 0.2;

/**
 * The modes in which the editor can be at any given time.
 * @enum {number}
 */
layermanager.earth.Mode = {
  // The editor is busy. This state covers fetching, parsing and loading KML,
  // as well as creating Plugin objects.
  LOADING: 1,
  // The editor failed not load.
  FAILED: 2,
  // The editor is displaying a layer and capturing clicks on entities.
  PICK: 3,
  // The editor is displaying the editing panel, but no geometry is being
  // edited. This state turns into EDIT when the user selects and geometry type
  // and clicks Create.
  CREATE: 4,
  // The editor is displaying an editable geometry object as well as the editing
  // panel.
  EDIT: 5,
  // The editor is displaying an editable Region object as well as the editing
  // panel.
  REGION: 6
};

/*******************************************************************************
*                               State Variables                                *
*******************************************************************************/

/**
 * The root Google Earth Plugin object, used to interface with lower-level
 * plugin features.
 * @type {GEPlugin}
 */
layermanager.earth.state.plugin = null;

/**
 * A reference to the main Google Earth Extensions library object, used to
 * interface with higher-level library functions built on top of the Earth
 * plugin API.
 * @type {GEarthExtensions}
 */
layermanager.earth.state.extensions = null;

/**
 * A reference to the Earth Plugin KmlFeature or KmlRegion object that is
 * currently being edited, or null if we're in picking mode or in creation mode
 * and haven't created a geometry yet.
 * @type {(KmlFeature|KmlRegion|null)}
 */
layermanager.earth.state.feature = null;

/**
 * The mode in which we are currently operating.
 * @type ?layermanager.earth.Mode
 */
layermanager.earth.state.mode = null;

/**
 * The ID of the last layer whose resources have been loaded.
 * @type ?number
 */
layermanager.earth.lastLoadedLayer = null;

/**
 * A table of resources, keyed by type then by URL.
 * @type Object.<string, Object.<string, Object>>
 */
layermanager.resources = {
  image: {},
  icon: {},
  model: {}
};

/*******************************************************************************
*                                     Main                                     *
*******************************************************************************/

/**
 * The main function that intializes the viewport and editing panel.
 */
layermanager.earth.initialize = function() {
  layermanager.earth.initViewport();
  layermanager.earth.initPanel();
};

/*******************************************************************************
*                                Public Events                                 *
*******************************************************************************/

/**
 * Signals an entity being picked while in picking mode.
 * @param {string} entity_id The numeric ID of the entity that was picked. It is
 *     assumed that all entity IDs are numbers prefixed with "id".
 */
layermanager.earth.api.reportEntityPicked = jQuery.noop;

/**
 * Signals the Set View button being clicked.
 * @param {Object.<string, number>} view A description of the current viewport.
 *     Contains longitude, latitude, altitude, heading, tilt and range values.
 */
layermanager.earth.api.reportViewSet = jQuery.noop;

/**
 * Signals the Set Geometry button being clicked.
 * @param {string} type The type of geometry being set. One of Point,
 *     LineString, Polygon, Model or GroundOverlay.
 * @param {Object} properties A description of the geometry's properties. The
 *     exact fields passed depend on the type of geometry.
 */
layermanager.earth.api.reportGeometrySet = jQuery.noop;

/**
 * Signals the region being edited having any of its bounds changed.
 * @param {number} north The north edge of the region, in degrees of latitude.
 * @param {number} south The south edge of the region, in degrees of latitude.
 * @param {number} east The east edge of the region, in degrees of longitude.
 * @param {number} west The west edge of the region, in degrees of longitude.
 * @param {number} altitude The altitude of the region, in meters.
 */
layermanager.earth.api.reportRegionChanged = jQuery.noop;

/*******************************************************************************
*                                Public Methods                                *
*******************************************************************************/

/**
 * Moves the camera to a certain position and orientation in the scene.
 * @param {number} latitude The latitude of the spot to which the camera will
 *     point, in degrees.
 * @param {number} longitude The longitude of the spot to which the camera will
 *     point, in degrees.
 * @param {number} range The distance, in meters, betweem the camera and the
 *     spot at which it will point.
 * @param {number=} opt_altitude The altitude of the spot to which the camera
 *     points, in meters.
 * @param {number=} opt_heading The direction at which the camera points, in
 *     degrees around the planet's normal.
 * @param {number=} opt_tilt The angle between the line connecting the camera
 *     with the spot at which it points and the planet's normal, in degrees. 0
 *     is straight down.
 */
layermanager.earth.api.setView = function(
    latitude, longitude, range, opt_altitude, opt_heading, opt_tilt) {
  var lookAt = layermanager.earth.state.plugin.createLookAt('');
  lookAt.set(latitude,
             longitude,
             opt_altitude || 0,
             layermanager.earth.state.plugin.ALTITUDE_RELATIVE_TO_GROUND,
             opt_heading || 0,
             opt_tilt || 0,
             range);
  layermanager.earth.state.plugin.getView().setAbstractView(lookAt);
};

/**
 * Fetches the KML of a layer and loads it, then attaches event handlers to all
 * entities that forward clicks on them to reportEntityPicked(). Models and
 * Ground Overlays are not clickable, so they get dummy placemarks attached for
 * picking. While the layer is being fetched and loading, state is switched to
 * Mode.LOADING. Once it's complete, state is switched to Mode.PICK.
 * @param {(number|string)} layerId The ID of the layer to load.
 * @param {function()=} opt_callback A parameterless function to call once the
 *     layer is loaded.
 */
layermanager.earth.api.loadLayerForPicking = function(layerId, opt_callback) {
  layermanager.earth.resetEditor();
  layermanager.earth.state.mode = layermanager.earth.Mode.LOADING;
  layermanager.earth.refreshPanel();

  var url = layermanager.earth.LAYER_KML_URL.replace('{ID}', layerId);
  url += '?compress=no&t=' + Date.now();  // Prevent compression and caching.
  jQuery.get(url, function(kmlString) {
    var kmlDocument = layermanager.earth.state.plugin.parseKml(kmlString);
    layermanager.earth.state.plugin.getFeatures().appendChild(kmlDocument);
    layermanager.earth.flyToFeature(kmlDocument);
    layermanager.earth.state.extensions.dom.walk(function() {
      var type = layermanager.earth.getFeatureType(this);
      var strippedType = layermanager.earth.stripKmlPrefix(type);

      var featureToSelect = this;
      var featureToReceiveClick = this;
      switch (type) {
        case 'KmlModel':
        case 'KmlGroundOverlay':
          var center = layermanager.earth.getLocation(this);
          var locationSource = this.getGeometry ? this.getGeometry() : this;
          center = [center.latitude, center.longitude, center.altitude];
          var point = (
              layermanager.earth.state.extensions.dom.buildPointPlacemark({
            point: center,
            altitudeMode: locationSource.getAltitudeMode()
          }, {
            name: strippedType + ': ' + this.getName(),
            icon: (type == 'KmlModel') ? layermanager.earth.MODEL_ICON_URL :
                                         layermanager.earth.OVERLAY_ICON_URL
          }));
          featureToReceiveClick = point;
          layermanager.earth.state.plugin.getFeatures().appendChild(point);
          // Intended fallthrough.
        case 'KmlPoint':
        case 'KmlPolygon':
        case 'KmlLineString':
        case 'KmlPhotoOverlay':
        case 'KmlMultiGeometry':
          layermanager.earth.registerEarthEvent(
              featureToReceiveClick, 'click', function(event) {
            layermanager.earth.api.reportEntityPicked(
                featureToSelect.getId().match(/^id(\d+)(?:_\d+)?$/)[1]);
            event.preventDefault();
          });
          break;
        default:
          // Lots of other different types that we don't worry about.
      }
    });
    layermanager.earth.state.mode = layermanager.earth.Mode.PICK;
    layermanager.earth.loadResourcesList(layerId);
    layermanager.earth.refreshPanel();
    (opt_callback || jQuery.noop)();
  }, 'text');
};

/**
 * Loads a feature described by the supplied KML into the editor, then switches
 * the mode to Mode.EDIT.
 * @param {string} type The type of the geometry to load. Valid values are
 *     Point, Model, LineString, Polygon and GroundOverlay.
 * @param {Object} properties An object describing the details of the geometry,
 *     in the same format as that returned by reportGeometrySet().
 * @param {function()=} opt_callback A function to call once the KML is loaded.
 */
layermanager.earth.api.loadGeometryForEditing = function(
    type, properties, opt_callback) {
  var dom = layermanager.earth.state.extensions.dom;
  var kmlFeature;

  // Make sure we work on a copy.
  properties = jQuery.extend(true, {}, properties);

  properties.altitude_mode = layermanager.earth.parseAltitudeMode(
      properties.altitude_mode) || 0;
  switch (type) {
    case 'Point':
      var point = properties.location;
      if (properties.altitude) point.push(properties.altitude);
      kmlFeature = dom.buildPointPlacemark({point: {
        point: point,
        altitudeMode: properties.altitude_mode,
        extrude: Boolean(properties.extrude)
      }});
      break;
    case 'LineString':
      var points = properties.points;
      if (properties.altitudes && properties.altitudes.length) {
        jQuery.each(points, function(index) {
          points[index].push(properties.altitudes[index] || 0);
        });
      }
      kmlFeature = dom.buildLineStringPlacemark({lineString: {
        path: points,
        altitudeMode: properties.altitude_mode,
        extrude: Boolean(properties.extrude),
        tessellate: Boolean(properties.tessellate)
      }});
      break;
    case 'Polygon':
      var points = properties.outer_points;
      if (properties.outer_altitudes && properties.outer_altitudes.length) {
        jQuery.each(points, function(index) {
          points[index].push(properties.outer_altitudes[index] || 0);
        });
      }
      kmlFeature = dom.buildPolygonPlacemark({polygon: {
        polygon: points,
        altitudeMode: properties.altitude_mode,
        extrude: Boolean(properties.extrude),
        tessellate: Boolean(properties.tessellate)
      }});
      break;
    case 'Model':
      if (properties.altitude) properties.location.push(properties.altitude);
      var url = layermanager.earth.getResolvedResourceUrl(properties.model);
      kmlFeature = dom.buildPlacemark({model: {
        link: url,
        location: properties.location,
        scale: [
          properties.scale_x || 1,
          properties.scale_y || 1,
          properties.scale_z || 1
        ],
        orientation: {
          heading: properties.heading || 0,
          tilt: properties.tilt || 0,
          roll: properties.roll || 0
        }
      }});
      break;
    case 'GroundOverlay':
      var url = layermanager.earth.getResolvedResourceUrl(properties.image);
      kmlFeature = dom.buildGroundOverlay(url, {
        box: {
          north: properties.north,
          south: properties.south,
          east: properties.east,
          west: properties.west,
          rotation: properties.rotation || 0
        },
        altitude: properties.altitude || 0,
        altitudeMode: properties.altitude_mode,
        color: properties.color || 'FFFFFFFF'
      });
      break;
    case 'PhotoOverlay':
      layermanager.earth.showError(
          'Photo overlays are not currently editable.');
      return;
    default:
      layermanager.earth.showError('Attempted to edit unknown geometry.');
      return;
  }

  layermanager.earth.resetEditor();
  layermanager.earth.state.plugin.getFeatures().appendChild(kmlFeature);
  kmlFeature.setName('');
  kmlFeature.setRegion(null);
  kmlFeature.setSnippet('');
  kmlFeature.setStyleUrl('');
  var buildStyle = layermanager.earth.state.extensions.dom.buildStyle;
  kmlFeature.setStyleSelector(buildStyle(layermanager.earth.DEFAULT_STYLE));
  layermanager.earth.flyToFeature(kmlFeature);
  layermanager.earth.initFeatureEditing(kmlFeature);
  layermanager.earth.state.mode = layermanager.earth.Mode.EDIT;
  layermanager.earth.refreshPanel();
  (opt_callback || jQuery.noop)();
};

/**
 * Creates a region as specified by the parameters and loads it into the editor.
 * Switches mode to Mode.REGION.
 * @param {number} north The north edge of the region, in degrees of latitude.
 * @param {number} south The south edge of the region, in degrees of latitude.
 * @param {number} east The east edge of the region, in degrees of longitude.
 * @param {number} west The west edge of the region, in degrees of longitude.
 * @param {number} altitude The altitude of the region, in meters.
 * @param {string} altitudeMode A choice of how to interpret the altitude
 *     argument, one of clampToGround, relativeToGround or absolute. Due to
 *     Earth's treatment of ground overlays, relativeToGround is interpreted as
 *     absolute for display purposes.
 * @param {boolean} flyToRegion Whether to reset the view to center on the new
 *     region.
 */
layermanager.earth.api.loadRegionForEditing = function(
    north, south, east, west, altitude, altitudeMode, flyToRegion) {
  layermanager.earth.resetEditor();
  if (altitudeMode == 'relativeToGround') altitudeMode = 'absolute';

  var region = layermanager.earth.state.extensions.dom.buildGroundOverlay('', {
    box: {
      north: Math.max(north, south),
      south: Math.min(north, south),
      east: Math.max(east, west),
      west: Math.min(east, west)
    },
    color: '88AA3333',
    altitude: altitude || 0,
    altitudeMode: layermanager.earth.parseAltitudeMode(altitudeMode)
  });
  layermanager.earth.state.plugin.getFeatures().appendChild(region);
  if (flyToRegion) layermanager.earth.flyToFeature(region);

  var reportChanges = function() {
    var box = region.getLatLonBox();
    layermanager.earth.api.reportRegionChanged(box.getNorth(), box.getSouth(),
                                            box.getEast(), box.getWest(),
                                            region.getAltitude());
  };

  layermanager.earth.state.feature = region;
  var syncHandles = layermanager.earth.makeGroundOverlayResizable(function() {
    layermanager.earth.runSyncers();
    reportChanges();
  });
  layermanager.earth.makeSurfaceMoveable(function() {
    syncHandles();
    reportChanges();
  });
  layermanager.earth.makeVerticallyMoveable(reportChanges);
  syncHandles();
  layermanager.earth.registerSyncer(layermanager.earth.refreshFeatureInfo);
  layermanager.earth.registerEarthEvent(
      layermanager.earth.state.plugin.getView(), 'viewchange',
      layermanager.earth.runSyncers);
  layermanager.earth.runSyncers();

  layermanager.earth.state.mode = layermanager.earth.Mode.REGION;
  layermanager.earth.refreshPanel();
};

/**
 * Clears the editor and enables the editing panel. Also switches mode to
 * Mode.CREATE.
 */
layermanager.earth.api.startEntityCreation = function() {
  layermanager.earth.resetEditor();
  layermanager.earth.state.mode = layermanager.earth.Mode.CREATE;
  jQuery('#geometry_type').val('Point');
  layermanager.earth.refreshPanel();
};

/**
 * Makes the control window resizable.
 * @param {Object} iframe A jQuery-wrapped <iframe> from the container window
 *     which contains the control. This is the element which will be resized
 *     when the resizing handle is dragged.
 */
layermanager.earth.api.makeResizable = function(iframe) {
  var parentWindow = window.top;
  var foreignBody = iframe.closest('body');
  var handle = jQuery('<img src="' + layermanager.earth.RESIZE_HANDLE_URL +
                      '">').appendTo(foreignBody);
  var start = null;
  var startEditorSize = null;
  var minWidth = parseInt(iframe.css('min-width')) || 1;
  var minHeight = parseInt(iframe.css('min-height')) || 1;

  var syncHandle = function() {
    var position = iframe.position();
    var width = iframe.width();
    var height = iframe.height();
    handle.css({
      left: position.left + width - handle.width() + 2,
      top: position.top + height - handle.height() + 2
    });
  };

  var overlay = jQuery('<div>').css({
    opacity: 0, position: 'absolute', width: '100%', height: '100%',
    left: parentWindow.scrollX, top: parentWindow.scrollY, 'z-index': 999
  }).mousemove(function(event) {
    var newWidth = startEditorSize.width + event.screenX - start.x;
    var newHeight = startEditorSize.height + event.screenY - start.y;
    if (newWidth >= minWidth && newHeight >= minHeight) {
      iframe.css({width: newWidth, height: newHeight});
      syncHandle();
    }
  }).mouseup(function(event) {
    if (event.button == 0) jQuery(this).detach();
  });

  handle.css({position: 'absolute', cursor: 'se-resize'}).load(syncHandle);
  handle.mousedown(function(event) {
    if (event.button == 0) {
      overlay.appendTo(foreignBody);
      start = {x: event.screenX, y: event.screenY};
      startEditorSize = {width: iframe.width(), height: iframe.height()};
      event.preventDefault();
    }
  });
};

/**
 * Unloads the loaded layer, entity or region, disables the editing panel and
 * resets mode to null.
 */
layermanager.earth.api.clear = function() {
  layermanager.earth.resetEditor();
  layermanager.earth.state.mode = null;
  layermanager.earth.refreshPanel();
};

/**
 * Checks whether the control is ready to receive mode-switching function calls.
 * @return {boolean} Whether the control is ready to receive commands.
 */
layermanager.earth.api.isReady = function() {
  return Boolean(
      layermanager.earth.state.plugin &&
      layermanager.earth.state.extensions &&
      layermanager.earth.state.mode != layermanager.earth.Mode.LOADING);
};

/**
 * Whether the control has loaded successfully.
 * @return {(boolean|undefined)} Whether the control has loaded successfully. If
 *     The control is still loading, returns undefined.
 */
layermanager.earth.api.isLoaded = function() {
  if (layermanager.earth.state.mode === null) {
    return undefined;
  } else {
    return (layermanager.earth.state.mode != layermanager.earth.Mode.FAILED);
  }
};

/*******************************************************************************
*                                Initialization                                *
*******************************************************************************/

/**
 * Initializes the editor viewport by creating an Earth plugin instance with the
 * appropriate world (as specified by the world query parameter).
 */
layermanager.earth.initViewport = function() {
  var world = layermanager.earth.getQueryArg('world') || 'earth';
  var db;
  if (world == 'moon') {
    db = {database: 'http://khmdb.google.com/?db=moon'};
  } else if (world == 'mars') {
    db = {database: 'http://khmdb.google.com/?db=mars'};
  }
  google.earth.createInstance(
      'viewport',
      layermanager.earth.preparePluginAfterLoading,
      layermanager.earth.acknowledgePluginLoadFailure,
      db);
};

/**
 * Initializes the earth extensions object, specifies the basic plugin settings
 * and binds a window resize handler to keep the panel size static and resize
 * the viewport together with the window. If a layer_id query parameter is
 * specified, that layer is loaded for picking.
 * @param {GEPlugin} earth The loaded Google Earth plugin object.
 */
layermanager.earth.preparePluginAfterLoading = function(earth) {
  var world = layermanager.earth.getQueryArg('world') || 'earth';
  layermanager.earth.state.plugin = earth;
  layermanager.earth.state.extensions = new GEarthExtensions(earth);

  var options = earth.getOptions();
  if (world == 'sky') options.setMapType(earth.MAP_TYPE_SKY);
  options.setScaleLegendVisibility(true);
  options.setAtmosphereVisibility(true);
  options.setMouseNavigationEnabled(true);

  jQuery(window).resize(function() {
    var bottomBorder = jQuery('#viewport').css('border-bottom-width');
    var topBorder = jQuery('#viewport').css('border-bottom-width');
    var borders = (parseInt(bottomBorder) || 0) + (parseInt(topBorder) || 0);
    jQuery('#viewport').css({
      height: jQuery(window).height() - jQuery('#panel').height() - borders,
      width: jQuery(window).width()
    });
  }).resize();

  layermanager.earth.state.plugin.getWindow().setVisibility(true);
  var layerId = layermanager.earth.getQueryArg('layer_id');
  if (layerId) layermanager.earth.api.loadLayerForPicking(layerId);
};

/**
 * Handles the failure of the Earth plugin to load. Sets the state to failed and
 * logs the error.
 * @param {string} error The error that caused the plugin to fail loading.
 */
layermanager.earth.acknowledgePluginLoadFailure = function(error) {
  layermanager.earth.state.mode = layermanager.earth.Mode.FAILED;
  console.log('isSupported = ' + google.earth.isSupported());
  console.log('isInstalled = ' + google.earth.isInstalled());
  console.log('Error: ' + error);
};

/** Initializes the editing panel and its controls. */
layermanager.earth.initPanel = function() {
  jQuery('#controls td:nth-child(odd)').css('text-align', 'right');
  layermanager.earth.initShimmedColorPicker(jQuery('#color'));

  jQuery('#geometry_type').change(layermanager.earth.updateEditingControls);
  jQuery('#apply').click(layermanager.earth.applySettings);
  jQuery('#save_geometry').click(layermanager.earth.saveGeometry);
  jQuery('#save_viewport').click(layermanager.earth.saveView);

  layermanager.earth.refreshPanel();
  jQuery('#panel').show();
};

/*******************************************************************************
*                             Panel Event Handling                             *
*******************************************************************************/

/**
 * Updates the state of the editing panel buttons depending on the current
 * editor mode (layermanager.earth.state.mode) and fills the editing panel
 * fields with the properties from and the object currently being edited
 * (layermanager.earth.state.feature), if any.
 */
layermanager.earth.refreshPanel = function() {
  jQuery('#loader').toggle(
      layermanager.earth.state.mode == layermanager.earth.Mode.LOADING);
  jQuery('#picking_message').toggle(
      layermanager.earth.state.mode == layermanager.earth.Mode.PICK);
  jQuery('#region_message').toggle(
      layermanager.earth.state.mode == layermanager.earth.Mode.REGION);
  if (layermanager.earth.state.mode == layermanager.earth.Mode.CREATE ||
      layermanager.earth.state.mode == layermanager.earth.Mode.EDIT) {
    var visibility = 'visible';
  } else {
    var visibility = 'hidden';
  }
  jQuery('#entity_editor').css('visibility', visibility);

  if (layermanager.earth.state.mode == layermanager.earth.Mode.CREATE) {
    jQuery('#apply').val('Create');
  }

  var feature = layermanager.earth.state.feature;
  if (feature) {
    var type = layermanager.earth.getFeatureType(feature);
    type = layermanager.earth.stripKmlPrefix(type);
    jQuery('#geometry_type').val(type).change();

    if (feature.getColor && feature.getColor()) {
      var color = layermanager.format.ABGRToARGBColor(feature.getColor().get());
      var cssColor = '#' + color.slice(2);
      jQuery('#color').val(color).ColorPickerSetColor(color).css({
        'color': cssColor, 'background-color': cssColor
      });
    }

    if (feature.getIcon && feature.getIcon()) {
      var imageUrl = feature.getIcon().getHref();
      jQuery('#resource').val(layermanager.earth.getResourceId(imageUrl));
    } else if (feature.getGeometry && feature.getGeometry().getLink) {
      var modelUrl = feature.getGeometry().getLink().getHref();
      jQuery('#resource').val(layermanager.earth.getResourceId(modelUrl));
    }

    if (feature.getGeometry && feature.getGeometry().getExtrude) {
      jQuery('#extrude').attr('checked',
          feature.getGeometry().getExtrude());
    }

    if (feature.getGeometry && feature.getGeometry().getTessellate) {
      jQuery('#tessellate').attr('checked',
          feature.getGeometry().getTessellate());
    }
  }
};

/**
 * Refreshes the status labels that show the coordinates of the currently edited
 * object (if any).
 */
layermanager.earth.refreshFeatureInfo = function() {
  if (layermanager.earth.state.feature) {
    var pos = layermanager.earth.getLocation(layermanager.earth.state.feature);
    jQuery('#info_latitude').html(
        layermanager.format.formatLatitude(pos.latitude));
    jQuery('#info_longitude').html(
        layermanager.format.formatLongitude(pos.longitude));
    jQuery('#info_altitude').html(
        layermanager.format.formatAltitude(pos.altitude));
  }
};

/**
 * Updates the editing panel controls based on the type of geometry selected.
 * Enables controls that are relevant to the selected geometry type and disables
 * those that aren't. Also fills the resource drop-down with either 3D models
 * or images depending on the geometry type.
 */
layermanager.earth.updateEditingControls = function() {
  var resourceLabel = jQuery('label[for=resource]');
  var resource = jQuery('#resource');
  var colorLabel = jQuery('label[for=color]');
  var color = jQuery('#color');
  var tessellate = jQuery('#tessellate');
  var tessellateLabel = jQuery('label[for=tessellate]');
  var extrude = jQuery('#extrude');
  var extrudeLabel = jQuery('label[for=extrude]');
  var resourceEnabled = true;
  var colorEnabled = true;
  var tessellateEnabled = true;
  var extrudeEnabled = true;

  resource.html('');
  resourceLabel.text('Resource:');

  var type = jQuery('#geometry_type').val();
  switch (type) {
    case 'Point':
      resourceEnabled = colorEnabled = tessellateEnabled = false;
      break;
    case 'LineString':
    case 'Polygon':
      resourceEnabled = colorEnabled = false;
      break;
    case 'Model':
      colorEnabled = tessellateEnabled = extrudeEnabled = false;
      resourceLabel.text('Model:');
      jQuery.each(layermanager.resources.model, function(_, model) {
        resource.append('<option value="' + model.id + '">' +
                        model.name + '</option>');
      });
      break;
    case 'GroundOverlay':
      tessellateEnabled = extrudeEnabled = false;
      resourceLabel.text('Image:');
      jQuery.each(layermanager.resources.image, function(_, image) {
        resource.append('<option value="' + image.id + '">' +
                        image.name + '</option>');
      });
      break;
  }
  resource.attr('disabled', !resourceEnabled);
  color.attr('disabled', !colorEnabled);
  tessellate.attr('disabled', !tessellateEnabled);
  extrude.attr('disabled', !extrudeEnabled);
  resourceLabel.toggleClass('disabled', !resourceEnabled);
  colorLabel.toggleClass('disabled', !colorEnabled);
  tessellateLabel.toggleClass('disabled', !tessellateEnabled);
  extrudeLabel.toggleClass('disabled', !extrudeEnabled);

  if (!colorEnabled) color.val('');

  if (layermanager.earth.state.mode == layermanager.earth.Mode.EDIT) {
    var feature = layermanager.earth.state.feature;
    var currentFeatureType = layermanager.earth.getFeatureType(feature);
    currentFeatureType = layermanager.earth.stripKmlPrefix(currentFeatureType);
    if (currentFeatureType == type) {
      jQuery('#apply').val('Apply');
    } else {
      jQuery('#apply').val('Replace');
    }
  }
};

/**
 * Applies the settings currently selected in the editing panel on the object
 * being edited in the 3D editor viewport. "Applying" in this case may mean 3
 * different things:
 * 1. If we're in creation mode, a new object is created with the selected
 *    properties.
 * 2. If we're in editing mode, and the geometry type was not changed, updates
 *    the existing object with the changed properties (extrusion, color, etc.).
 * 3. If we're in editing mode, and the geometry type was changed, discards the
 *    existing object and creates a new one of the specified type with the
 *    specified properties.
 */
layermanager.earth.applySettings = function() {
  var state = layermanager.earth.state;
  if (state.mode == layermanager.earth.Mode.CREATE) {
    layermanager.earth.createGeometry();
  } else if (state.mode == layermanager.earth.Mode.EDIT) {
    var currentType = layermanager.earth.getFeatureType(state.feature);
    currentType = layermanager.earth.stripKmlPrefix(currentType);
    var selectedType = jQuery('#geometry_type').val();
    if (currentType == selectedType) {
      layermanager.earth.updateGeometry();
    } else {
      layermanager.earth.resetEditor();
      layermanager.earth.createGeometry();
    }
  } else {
    layermanager.earth.showError('Invalid action specified.');
  }
};

/**
 * Updates the properties of the geometry being edited with the values selected
 * in the editing panel.
 */
layermanager.earth.updateGeometry = function() {
  var feature = layermanager.earth.state.feature;
  if (!feature) return;

  if (feature.getColor) {
    var color = layermanager.format.ARGBToABGRColor(jQuery('#color').val());
    feature.getColor().set(color);
  }

  var url = layermanager.earth.getResolvedResourceUrl(
      jQuery('#resource').val());
  if (feature.getIcon && feature.getIcon()) {
    feature.getIcon().setHref(url);
  } else if (feature.getGeometry && feature.getGeometry().getLink) {
    feature.getGeometry().getLink().setHref(url);
  }

  if (feature.getGeometry && feature.getGeometry().getExtrude) {
    feature.getGeometry().setExtrude(jQuery('#extrude').is(':checked'));
  }

  if (feature.getGeometry && feature.getGeometry().getTessellate) {
    feature.getGeometry().setTessellate(jQuery('#tessellate').is(':checked'));
  }
};

/**
 * Creates a new geometry in the 3D editor based on the properties selected
 * in the editing panel.
 */
layermanager.earth.createGeometry = function() {
  var plugin = layermanager.earth.state.plugin;
  var extensions = layermanager.earth.state.extensions;
  var view = layermanager.earth.state.plugin.getView();
  var lookAt = view.copyAsLookAt(plugin.ALTITUDE_RELATIVE_TO_GROUND);
  var position = [lookAt.getLatitude(),
                  lookAt.getLongitude(),
                  lookAt.getAltitude()];
  var hitTest = function(left, top) {
    var result = view.hitTest(left, plugin.UNITS_FRACTION,
                              top, plugin.UNITS_FRACTION,
                              plugin.HIT_TEST_GLOBE);
    return [result.getLatitude(), result.getLongitude(), result.getAltitude()];
  };
  var margin = layermanager.earth.DEFAULT_NEW_GEOMETRY_SIZE / 2;
  var frameCorners = [hitTest(0.5 - margin, 0.5 - margin),
                      hitTest(0.5 - margin, 0.5 + margin),
                      hitTest(0.5 + margin, 0.5 + margin),
                      hitTest(0.5 + margin, 0.5 - margin)];
  var resourceUrl = layermanager.earth.getResolvedResourceUrl(
      jQuery('#resource').val());

  var type = jQuery('#geometry_type').val();
  var feature;
  var altitudeMode = plugin.ALTITUDE_RELATIVE_TO_GROUND;
  switch (type) {
    case 'Point':
      feature = extensions.dom.buildPointPlacemark(position);
      break;
    case 'LineString':
      feature = extensions.dom.buildLineStringPlacemark(frameCorners);
      break;
    case 'Polygon':
      feature = extensions.dom.buildPolygonPlacemark(frameCorners);
      break;
    case 'Model':
      if (!resourceUrl) {
        alert('Please select a 3D model resource.');
        return;
      }
      feature = extensions.dom.buildPlacemark({model: {link: resourceUrl}});
      break;
    case 'GroundOverlay':
      // The default relative to ground altitude mode is not supported for
      // ground overlay, and using absolute does not allow draping overlays over
      // terrain, which is the most common usage.
      var altitudeMode = plugin.ALTITUDE_CLAMP_TO_GROUND;
      if (!resourceUrl) {
        alert('Please select an image.');
        return;
      }
      feature = extensions.dom.buildGroundOverlay(resourceUrl, {box: {
        north: Math.max(frameCorners[0][0], frameCorners[2][0]),
        south: Math.min(frameCorners[0][0], frameCorners[2][0]),
        east: Math.max(frameCorners[0][1], frameCorners[2][1]),
        west: Math.min(frameCorners[0][1], frameCorners[2][1])
      }});
      break;
    default:
      layermanager.earth.showError('Attempted to create unknown geometry.');
      return;
  }
  layermanager.earth.state.plugin.getFeatures().appendChild(feature);
  var geometry = feature.getGeometry ? feature.getGeometry() : feature;
  geometry.setAltitudeMode(altitudeMode);
  var style = extensions.dom.buildStyle(layermanager.earth.DEFAULT_STYLE);
  feature.setStyleSelector(style);
  layermanager.earth.flyToFeature(feature);
  layermanager.earth.initFeatureEditing(feature);
  layermanager.earth.state.mode = layermanager.earth.Mode.EDIT;
  layermanager.earth.refreshPanel();
};

/**
 * Triggers the reportGeometrySet() event, passing it the type and properties of
 * the geometry currently in the 3D editor window.
 */
layermanager.earth.saveGeometry = function() {
  var feature = layermanager.earth.state.feature;
  if (!feature) {
    alert('No geometry is being edited.');
    return;
  }

  var type = layermanager.earth.getFeatureType(feature);
  var geometry = feature.getGeometry && feature.getGeometry();
  var location = layermanager.earth.getLocation(feature);
  var altitudeMode = (geometry || feature).getAltitudeMode();
  altitudeMode = layermanager.earth.describeAltitudeMode(altitudeMode);
  var details;
  switch (type) {
    case 'KmlPoint':
      details = {
        location: [location.latitude, location.longitude],
        altitude: location.altitude,
        altitude_mode: altitudeMode,
        extrude: geometry.getExtrude()
      };
      break;
    case 'KmlLineString':
      var points = [];
      var altitudes = [];
      var coordinates = geometry.getCoordinates();
      var pointsCount = coordinates.getLength();
      for (var i = 0; i < pointsCount; i++) {
        var point = coordinates.get(i);
        points.push([point.getLatitude(), point.getLongitude()]);
        altitudes.push(point.getAltitude());
      }
      details = {
        points: points,
        altitudes: altitudes,
        altitude_mode: altitudeMode,
        tessellate: geometry.getTessellate(),
        extrude: geometry.getExtrude()
      };
      break;
    case 'KmlPolygon':
      var points = [];
      var altitudes = [];
      var coordinates = geometry.getOuterBoundary().getCoordinates();
      var pointsCount = coordinates.getLength() - 1;
      for (var i = 0; i < pointsCount; i++) {
        var point = coordinates.get(i);
        points.push([point.getLatitude(), point.getLongitude()]);
        altitudes.push(point.getAltitude());
      }
      details = {
        outer_points: points,
        outer_altitudes: altitudes,
        altitude_mode: altitudeMode,
        tessellate: geometry.getTessellate(),
        extrude: geometry.getExtrude()
      };
      break;
    case 'KmlModel':
      var scale = geometry.getScale();
      var rotation = layermanager.earth.getRotation(feature);
      var url = geometry.getLink().getHref();
      var resourceId = layermanager.earth.getResourceId(url);
      details = {
        location: [location.latitude, location.longitude],
        altitude: location.altitude,
        altitude_mode: altitudeMode,
        model: resourceId,
        heading: rotation.heading,
        tilt: rotation.tilt,
        roll: rotation.roll,
        scale_x: scale.getX(),
        scale_y: scale.getY(),
        scale_z: scale.getZ()
      };
      break;
    case 'KmlGroundOverlay':
      var box = feature.getLatLonBox();
      details = {
        north: box.getNorth(),
        south: box.getSouth(),
        east: box.getEast(),
        west: box.getWest(),
        rotation: layermanager.earth.getRotation(feature).heading,
        altitude: location.altitude,
        altitude_mode: altitudeMode,
        image: layermanager.earth.getResourceId(feature.getIcon().getHref()),
        color: layermanager.util.ARGBToABGRColor(jQuery('#color').val())
      };
      break;
    default:
      layermanager.earth.showError('Tried to report invalid geometry type.');
      return;
  }
  if (type != null) {
    type = layermanager.earth.stripKmlPrefix(type);
    layermanager.earth.api.reportGeometrySet(type, details);
  }
};

/**
 * Triggers the reportViewSet() event with the description of the view currently
 * being displayed in the 3D viewport.
 */
layermanager.earth.saveView = function() {
  var view = layermanager.earth.state.plugin.getView();
  var lookAt = view.copyAsLookAt(
      layermanager.earth.state.plugin.ALTITUDE_RELATIVE_TO_GROUND);
  layermanager.earth.api.reportViewSet({
    view_longitude: lookAt.getLongitude(),
    view_latitude: lookAt.getLatitude(),
    view_altitude: lookAt.getAltitude(),
    view_heading: lookAt.getHeading(),
    view_tilt: lookAt.getTilt(),
    view_range: lookAt.getRange()
  });
};

/*******************************************************************************
*                               Geometry Editing                               *
*******************************************************************************/

/**
 * Rotates a 2D point around another.
 * @param {Object} point The point to rotate, which has latitude and longitude
 *     properties.
 * @param {boolean} reverse If true, rotate counter-clockwise.
 * @param {Object=} opt_center The point to rotate around. If not specified,
 *     the center of layermanager.earth.state.feature is used.
 * @return {Object} The rotate point.
 */
layermanager.earth.getRotatedPoint = function(point, reverse, opt_center) {
  if (!opt_center) {
    var location = layermanager.earth.getLocation(
        layermanager.earth.state.feature);
    opt_center = geo.linalg.Vector([location.latitude, location.longitude]);
  }
  var angle = layermanager.earth.getRotation(layermanager.earth.state.feature);
  angle = angle.heading.toRadians();
  angle *= (reverse ? -1 : 1);
  point = geo.linalg.Vector(point);
  var rotatedVector = point.rotate(angle, opt_center);
  return {
    latitude: rotatedVector.elements[0],
    longitude: rotatedVector.elements[1]
  };
};

/**
 * Calculates the location of the centerpoint of a KML Feature.
 * @param {KmlFeature} feature The feature whose centerpoint is to be found.
 * @return {Object} The calculated centerpoint, with latitude, longitude and
 *     altitude properties.
 */
layermanager.earth.getLocation = function(feature) {
  var geometry = (feature.getGeometry ? feature.getGeometry() : feature);
  var type = geometry.getType();
  switch (type) {
    case 'KmlModel':
      geometry = geometry.getLocation();
      // Intended falthrough.
    case 'KmlPoint':
      return {
        latitude: geometry.getLatitude(),
        longitude: geometry.getLongitude(),
        altitude: geometry.getAltitude()
      };
    case 'KmlPolygon':
      geometry = geometry.getOuterBoundary();
      // Intended falthrough.
    case 'KmlLineString':
      var sumLatitude = 0;
      var sumLongitude = 0;
      var sumAltitude = 0;
      var coordinates = geometry.getCoordinates();
      var pointsCount = coordinates.getLength();
      for (var i = 0; i < pointsCount; i++) {
        var point = coordinates.get(i);
        sumLatitude += point.getLatitude();
        sumLongitude += point.getLongitude();
        sumAltitude += point.getAltitude();
      }
      return {
        latitude: sumLatitude / pointsCount,
        longitude: sumLongitude / pointsCount,
        altitude: sumAltitude / pointsCount
      };
    case 'KmlGroundOverlay':
      var box = geometry.getLatLonBox();
      return {
        latitude: (box.getNorth() + box.getSouth()) / 2,
        longitude: (box.getEast() + box.getWest()) / 2,
        altitude: feature.getAltitude()
      };
    default:
      var computeBounds = layermanager.earth.state.extensions.dom.computeBounds;
      var location = computeBounds(feature).getCenter();
      if (location) {
        return {
          latitude: location.lat(),
          longitude: location.lng(),
          altitude: location.altitude()
        };
      } else {
        return {latitude: 0, longitude: 0, altitude: 0};
      }
  }
};

/**
 * Retrieves the rotation of a feature.
 * @param {KmlFeature} feature The feature whose rotation is to be found.
 * @return {?Object} The rotation, with heading, tilt and roll properties. If
 *     the chosen feature does not have rotation (e.g. a point), returns null.
 */
layermanager.earth.getRotation = function(feature) {
  var geometry = (feature.getGeometry ? feature.getGeometry() : feature);
  var type = geometry.getType();
  switch (type) {
    case 'KmlModel':
      var orientation = geometry.getOrientation();
      return {
        heading: orientation.getHeading() % 360,
        tilt: orientation.getTilt() % 360,
        roll: orientation.getRoll() % 360
      };
    case 'KmlGroundOverlay':
      return {
        heading: geometry.getLatLonBox().getRotation() % 360,
        tilt: 0,
        roll: 0
      };
    default:
      console.log('Could not get rotation for ' + type);
      return null;
  }
};

/**
 * Moves a KmlFeature to the specified location.
 * @param {KmlFeature} feature The feature to move.
 * @param {number=} opt_latitude The latitude to move to.
 * @param {number=} opt_longitude The longitude to move to.
 * @param {number=} opt_altitude The altitude to move to.
 */
layermanager.earth.setLocation = function(
    feature, opt_latitude, opt_longitude, opt_altitude) {
  var location = layermanager.earth.getLocation(feature);
  var deltaLatitude = (opt_latitude === undefined) ?
                      null : opt_latitude - location.latitude;
  var deltaLongitude = (opt_longitude === undefined) ?
                       null : opt_longitude - location.longitude;
  var deltaAltitude = (opt_altitude === undefined) ?
                      null : opt_altitude - location.altitude;
  var geometry = (feature.getGeometry ? feature.getGeometry() : feature);
  var type = geometry.getType();
  switch (type) {
    case 'KmlModel':
      geometry = geometry.getLocation();
      // Intended falthrough.
    case 'KmlPoint':
      if (deltaLatitude) {
        geometry.setLatitude(geometry.getLatitude() + deltaLatitude);
      }
      if (deltaLongitude) {
        geometry.setLongitude(geometry.getLongitude() + deltaLongitude);
      }
      if (deltaAltitude) {
        geometry.setAltitude(geometry.getAltitude() + deltaAltitude);
      }
      break;
    case 'KmlPolygon':
      geometry = geometry.getOuterBoundary();
      // Intended falthrough.
    case 'KmlLineString':
      var coordinates = geometry.getCoordinates();
      for (var i = 0; i < coordinates.getLength(); i++) {
        var point = coordinates.get(i);
        if (deltaLatitude) {
          point.setLatitude(point.getLatitude() + deltaLatitude);
        }
        if (deltaLongitude) {
          point.setLongitude(point.getLongitude() + deltaLongitude);
        }
        if (deltaAltitude) {
          point.setAltitude(point.getAltitude() + deltaAltitude);
        }
        coordinates.set(i, point);
      }
      break;
    case 'KmlGroundOverlay':
      var box = geometry.getLatLonBox();
      if (deltaLatitude) {
        box.setNorth(box.getNorth() + deltaLatitude);
        box.setSouth(box.getSouth() + deltaLatitude);
      }
      if (deltaLongitude) {
        box.setEast(box.getEast() + deltaLongitude);
        box.setWest(box.getWest() + deltaLongitude);
      }
      if (deltaAltitude) {
        geometry.setAltitude(geometry.getAltitude() + deltaAltitude);
      }
      break;
    default:
      console.log('Could not alter position for ' + type);
  }
  layermanager.earth.runSyncers();
};

/**
 * Sets the rotation of a feature.
 * @param {KmlFeature} feature The feature to rotate.
 * @param {number=} opt_heading The rotation in degrees around the Z axis normal
 *     to the surface of the planet.
 * @param {number=} opt_tilt The rotation in degrees around the X axis.
 * @param {number=} opt_roll The rotation in degrees around the Y axis.
 */
layermanager.earth.setRotation = function(
    feature, opt_heading, opt_tilt, opt_roll) {
  var geometry = (feature.getGeometry ? feature.getGeometry() : feature);
  var type = geometry.getType();
  switch (type) {
    case 'KmlModel':
      var orientation = geometry.getOrientation();
      if (opt_heading !== undefined) orientation.setHeading(opt_heading);
      if (opt_tilt !== undefined) orientation.setTilt(opt_tilt);
      if (opt_roll !== undefined) orientation.setRoll(opt_roll);
      break;
    case 'KmlGroundOverlay':
      if (opt_heading !== undefined) {
        geometry.getLatLonBox().setRotation(opt_heading);
      }
      break;
    default:
      console.log('Could not set rotation for ' + type);
  }
  layermanager.earth.runSyncers();
};

/**
 * Makes the specified feature editable by the user. The exact change
 * depends on the type of feature, but most include 3D dragging, some
 * form of resizing, and rotation.
 * @param {KmlFeature} feature The feature to make editable.
 */
layermanager.earth.initFeatureEditing = function(feature) {
  layermanager.earth.state.feature = feature;

  var preventDefault = layermanager.earth.preventDefault;
  switch (layermanager.earth.getFeatureType(feature)) {
    case 'KmlPoint':
      layermanager.earth.registerEarthEvent(feature, 'click', preventDefault);
      layermanager.earth.registerEarthEvent(feature, 'mouseover',
                                            preventDefault);
      layermanager.earth.makeSurfaceMoveable();
      layermanager.earth.makeVerticallyMoveable();
      break;
    case 'KmlLineString':
      layermanager.earth.registerEarthEvent(feature, 'click', preventDefault);
      var makeEditable = function() {
        layermanager.earth.state.extensions.edit.editLineString(
            feature.getGeometry(),
            {editCallback: layermanager.earth.runSyncers});
      };
      makeEditable();
      layermanager.earth.makeSurfaceMoveable(makeEditable);
      layermanager.earth.makeVerticallyMoveable(makeEditable);
      break;
    case 'KmlPolygon':
      layermanager.earth.registerEarthEvent(feature, 'click', preventDefault);
      var makeEditable = function() {
        var ring = feature.getGeometry().getOuterBoundary();
        layermanager.earth.state.extensions.edit.editLineString(ring, {
          editCallback: layermanager.earth.runSyncers
        });
      };
      makeEditable();
      layermanager.earth.makeSurfaceMoveable(makeEditable);
      layermanager.earth.makeVerticallyMoveable(makeEditable);
      break;
    case 'KmlModel':
      layermanager.earth.makeSurfaceMoveable();
      layermanager.earth.makeVerticallyMoveable();
      layermanager.earth.makeZRotateable();
      layermanager.earth.makeModelScalable();
      break;
    case 'KmlGroundOverlay':
      var syncer = layermanager.earth.makeGroundOverlayResizable(
          layermanager.earth.runSyncers);
      layermanager.earth.makeSurfaceMoveable(syncer);
      layermanager.earth.makeVerticallyMoveable();
      layermanager.earth.makeZRotateable(syncer);
      syncer();
      break;
    case 'KmlPhotoOverlay':
      layermanager.earth.showError(
          'Photo Overlay editing is not available yet.');
      return;  // Skip the interval/event registrations!
    default:
      layermanager.earth.showError('Unidentified geometry type loaded!');
      return;
  }

  layermanager.earth.registerSyncer(layermanager.earth.refreshFeatureInfo);
  layermanager.earth.registerEarthEvent(
      layermanager.earth.state.plugin.getView(), 'viewchange',
      layermanager.earth.runSyncers);
  layermanager.earth.runSyncers();
};

/**
 * Creates a control widget screen overlay with the specified icon, position
 * and drag/drop event handlers. Also registers a syncer that makes synchronizes
 * the on-screen position of the widget with the position of the currently
 * edited feature.
 * @param {Object} displayOptions An object describing the appearance of the
 *     widget. See layermanager.earth.MOVE_WIDGET for the format.
 * @param {function(number, number, Event)} dragCallback A handler for the
 *     dragging event. Passed the screen coordinates of the point where the drag
 *     operation started as well as a standard Event that contains info about
 *     the point over which the cursor is currently passing.
 * @param {function()=} opt_dropCallback A handler to call when a drag operation
 *     is finished.
 */
layermanager.earth.makeWidget = function(
    displayOptions, dragCallback, opt_dropCallback) {
  // Create overlays.
  var buildOverlay = layermanager.earth.state.extensions.dom.buildScreenOverlay;
  var defaultOptions = {
    overlayXY: {top: 0, left: 0},
    screenXY: {top: 0, left: 0},
    size: {width: displayOptions.width, height: displayOptions.height}
  };
  var normalOptions = jQuery.extend({visibility: true}, defaultOptions);
  var overOptions = jQuery.extend(
      {drawOrder: 1, visibility: false}, defaultOptions);
  var iconOverlay = buildOverlay(
      displayOptions.normal, normalOptions);
  var iconOverOverlay = buildOverlay(
      displayOptions.over, overOptions);

  // Insert overlays.
  layermanager.earth.state.plugin.getFeatures().appendChild(iconOverlay);
  layermanager.earth.state.plugin.getFeatures().appendChild(iconOverOverlay);

  // Make sure the icon stays next to the feature.
  // screenXY and overlayXY are switched due to an API bug:
  // http://code.google.com/p/earth-api-samples/issues/detail?id=193
  var iconXY = iconOverlay.getOverlayXY();
  var iconOverXY = iconOverOverlay.getOverlayXY();
  layermanager.earth.registerSyncer(function(screenPoint) {
    var newX = screenPoint.getX() + displayOptions.x;
    var newY = screenPoint.getY() + displayOptions.y;
    iconXY.setX(newX);
    iconXY.setY(newY);
    iconOverXY.setX(newX);
    iconOverXY.setY(newY);
  });

  // Setup dragging events.
  var window = layermanager.earth.state.plugin.getWindow();
  var isMouseOver = false;
  var dragStartX, dragStartY;
  var limitedDragCallback = layermanager.earth.limitCallFrequency(dragCallback);
  layermanager.earth.registerEarthEvent(window, 'mousemove', function(event) {
    if (dragStartX === undefined) {
      var eventX = event.getClientX()
      var eventY = event.getClientY();
      var iconX = iconXY.getX()
      var iconY = iconXY.getY();
      var oldIsMouseOver = isMouseOver;
      isMouseOver = (eventX >= iconX && eventY >= iconY &&
                     eventX < iconX + displayOptions.width &&
                     eventY < iconY + displayOptions.height);
      if (oldIsMouseOver != isMouseOver) {
        iconOverOverlay.setVisibility(isMouseOver);
      }
    } else {
      limitedDragCallback(dragStartX, dragStartY, event);
    }
    event.preventDefault();
  });
  layermanager.earth.registerEarthEvent(window, 'mousedown', function(event) {
    if (isMouseOver && event.getButton() === 0) {
      dragStartX = event.getClientX();
      dragStartY = event.getClientY();
      event.preventDefault();
    }
  });
  layermanager.earth.registerEarthEvent(window, 'mouseup', function(event) {
    if (event.getButton() === 0 && dragStartX !== undefined) {
      dragStartX = dragStartY = undefined;
      (opt_dropCallback || jQuery.noop)();
      event.preventDefault();
    }
  });
};

/**
 * Adds a moving widget to the currently edited feature that allows the user to
 * drag the feature to move it over the surface of the planet, updating its
 * latitude and longitude via setLocation().
 * @param {function()=} opt_dropCallback A handler to call when a drag/move
 *     operation is finished.
 */
layermanager.earth.makeSurfaceMoveable = function(opt_dropCallback) {
  var plugin = layermanager.earth.state.plugin;
  var view = plugin.getView();
  layermanager.earth.makeWidget(
      layermanager.earth.MOVE_WIDGET, function(_, __, event) {
    var landPoint = view.hitTest(event.getClientX(), plugin.UNITS_PIXELS,
                                 event.getClientY(), plugin.UNITS_PIXELS,
                                 plugin.HIT_TEST_GLOBE |
                                 plugin.HIT_TEST_TERRAIN |
                                 plugin.HIT_TEST_BUILDINGS);
    if (landPoint) {
      layermanager.earth.setLocation(layermanager.earth.state.feature,
                                  landPoint.getLatitude(),
                                  landPoint.getLongitude());
    }
  }, opt_dropCallback);
};

/**
 * Adds a moving widget to the currently edited feature that allows the user to
 * drag the feature to move it up and down, above and below the surface of the
 * planet, updating its altitude via setLocation().
 * @param {function()=} opt_dropCallback A handler to call when a drag/move
 *     operation is finished.
 */
layermanager.earth.makeVerticallyMoveable = function(opt_dropCallback) {
  var view = layermanager.earth.state.plugin.getView();
  var originalAltitude = null;
  layermanager.earth.makeWidget(
      layermanager.earth.ALTITUDE_WIDGET, function(_, dragStartY, event) {
    if (originalAltitude === null) {
      originalAltitude = layermanager.earth.getLocation(
          layermanager.earth.state.feature).altitude;
    }
    var delta = dragStartY - event.getClientY();
    var camera = view.copyAsCamera(
        layermanager.earth.state.plugin.ALTITUDE_RELATIVE_TO_GROUND);
    var multiplier = camera.getAltitude() * layermanager.earth.ALTITUDE_RATE;
    layermanager.earth.setLocation(layermanager.earth.state.feature,
        undefined, undefined, originalAltitude + delta * multiplier);
  }, function() {
    originalAltitude = null;
    (opt_dropCallback || jQuery.noop)();
  });
};

/**
 * Adds a rotation widget to the currently edited feature that allows the user
 * to rotate the object around an axis normal to the surface of the planet,
 * updating its rotation via setRotation().
 * @param {function()=} opt_dropCallback A handler to call when a drag/rotate
 *     operation is finished.
 */
layermanager.earth.makeZRotateable = function(opt_dropCallback) {
  var view = layermanager.earth.state.plugin.getView();
  var originalRotation = null;
  layermanager.earth.makeWidget(
      layermanager.earth.ROTATE_WIDGET, function(dragStartX, _, event) {
    if (originalRotation === null) {
      originalRotation = layermanager.earth.getRotation(
          layermanager.earth.state.feature).heading;
    }
    var delta = dragStartX - event.getClientX();
    var adjustedDelta = delta * layermanager.earth.ROTATE_RATE;
    layermanager.earth.setRotation(
        layermanager.earth.state.feature, originalRotation + adjustedDelta);
  }, function() {
    originalRotation = null;
    (opt_dropCallback || jQuery.noop)();
  });
};

/**
 * Adds a scaling widget to the currently edited feature that allows the user
 * to uniformly scale the object. Works only on features that have a Scale,
 * which at the time of writing is only 3D models.
 * @param {function()=} opt_dropCallback A handler to call when a drag/rotate
 *     operation is finished.
 */
layermanager.earth.makeModelScalable = function(opt_dropCallback) {
  var view = layermanager.earth.state.plugin.getView();
  var originalScale = null;
  var model = layermanager.earth.state.feature.getGeometry();
  layermanager.earth.makeWidget(
      layermanager.earth.SCALE_WIDGET, function(_, dragStartY, event) {
    var scaleObject = model.getScale();
    if (originalScale === null) originalScale = scaleObject.getX();
    var delta = dragStartY - event.getClientY();
    var camera = view.copyAsCamera(
        layermanager.earth.state.plugin.ALTITUDE_RELATIVE_TO_GROUND);
    var multiplier = camera.getAltitude() * layermanager.earth.SCALE_RATE;
    var newScale = originalScale + delta * multiplier;
    if (newScale < 0) newScale = scaleObject.getX();
    scaleObject.setX(newScale);
    scaleObject.setY(newScale);
    scaleObject.setZ(newScale);
  }, function() {
    originalScale = null;
    (opt_dropCallback || jQuery.noop)();
  });
};

/**
 * Adds two resizing handles to the currently edited ground overlay. The
 * resizing is applied by adjusting the overlay's north/south/east/west bounds
 * acquired via getLatLonBox().
 * @param {function()=} opt_dropCallback A handler to call when a drag/resize
 *     operation is finished.
 * @return {function()} A synchronization function that moves the resizing
 *     handles to the appropriate corners of the ground overlay. Should be
 *     called whenever another function modifies the ground overlay's bounds
 *     change.
 */
layermanager.earth.makeGroundOverlayResizable = function(opt_dropCallback) {
  var box = layermanager.earth.state.feature.getLatLonBox();
  var corners = [['North', 'East'], ['South', 'West']];
  var syncers = [];
  var placemarks = [];

  // Create handles and syncers which update the location of the handles when
  // the overlay is rotated.
  jQuery.each(corners, function(_, corner) {
    var coordinates = [box['get' + corner[0]](), box['get' + corner[1]]()];
    var placemark = layermanager.earth.state.extensions.dom.buildPointPlacemark(
      coordinates, {icon: {href: layermanager.earth.CROSSHAIR_ICON_URL}});
    var point = placemark.getGeometry();
    layermanager.earth.state.plugin.getFeatures().appendChild(placemark);
    layermanager.earth.registerEarthEvent(
        placemark, 'mouseover', layermanager.earth.preventDefault);
    syncers.push(function() {
      var coordinates = [box['get' + corner[0]](), box['get' + corner[1]]()];
      var rotated = layermanager.earth.getRotatedPoint(coordinates, true);
      point.setLatitude(rotated.latitude);
      point.setLongitude(rotated.longitude);
    });
    placemarks.push(placemark);
  });

  // Make the handles draggable and propagate their position to the bounds of
  // the overlay. Note that the points need to be unrotated when the overlay is
  // rotated to find the bounds that need to be applied.
  jQuery.each(corners, function(index, corner) {
    layermanager.earth.state.extensions.edit.makeDraggable(placemarks[index], {
      bounce: false,
      dragCallback: layermanager.earth.limitCallFrequency(function() {
        var point = placemarks[index].getGeometry();
        var otherPoint = placemarks[index ? 0 : 1].getGeometry();
        var center = [(point.getLatitude() + otherPoint.getLatitude()) / 2,
                      (point.getLongitude() + otherPoint.getLongitude()) / 2];
        var location = [point.getLatitude(), point.getLongitude()];
        location = layermanager.earth.getRotatedPoint(location, false, center);
        var otherLocation = [otherPoint.getLatitude(),
                             otherPoint.getLongitude()];
        otherLocation = layermanager.earth.getRotatedPoint(
            otherLocation, false, center);
        var otherCorner = corners[index ? 0 : 1];
        box['set' + corner[0]](location.latitude);
        box['set' + corner[1]](location.longitude);
        box['set' + otherCorner[0]](otherLocation.latitude);
        box['set' + otherCorner[1]](otherLocation.longitude);
      }),
      dropCallback: (opt_dropCallback || jQuery.noop)
    });
  });

  return function() {
    syncers[0]();
    syncers[1]();
  };
};

/*******************************************************************************
*                             Scheduling Utilities                             *
*******************************************************************************/

/**
 * Registers a Google Earth plugin event handler, and remembers it so that it
 * can be cleared layter via clearEarthEvents().
 * @param {Object} object The GE plugin object whose events are to be watched.
 * @param {string} eventType The type of event to watch.
 * @param {function(Event)} handler The event handler.
 */
layermanager.earth.registerEarthEvent = function(object, eventType, handler) {
  google.earth.addEventListener(object, eventType, handler);
  layermanager.earth.registeredEarthEvents_.push([object, eventType, handler]);
};
/**
 * The Earth plugin events registered so far. Kept for clearing later.
 * @type {Array}
 * @private
 */
layermanager.earth.registeredEarthEvents_ = [];

/**
 * Removes all Google Earth plugin events previously registered via
 * registerEarthEvent().
 */
layermanager.earth.clearEarthEvents = function() {
  jQuery.each(layermanager.earth.registeredEarthEvents_, function(_, event) {
    try {
      google.earth.removeEventListener(event[0], event[1], event[2]);
    } catch (e) {
      // Ignore errors resulting from previously destroyed objects.
    }
  });
  layermanager.earth.registeredEarthEvents_ = [];
};

/**
 * Registers a synchronization function that runs regularly. Used mainly to
 * synchronize widget overlays with the feature being edited.
 * @param {function(KmlVec2)} syncer The synchronization function. Passed the
 *     location of the center of layermanager.earth.state.feature in screen
 *     coordinates.
 */
layermanager.earth.registerSyncer = function(syncer) {
  layermanager.earth.registeredSyncers_.push(syncer);
};
/**
 * The synchronization functions registered to be run by runSyncers().
 * @type {Array}
 * @private
 */
layermanager.earth.registeredSyncers_ = [];

/**
 * Clears the list of synchronization functions previously registered via
 * registerSyncer().
 */
layermanager.earth.clearSyncers = function() {
  layermanager.earth.registeredSyncers_ = [];
};

/**
 * Executes all the synchronization functions previously registered via
 * registerSyncer(). Each function is passed the coordinates of the screen point
 * to which the location of the currently edited feature projects.
 */
layermanager.earth.runSyncers = function() {
  var location = layermanager.earth.getLocation(
    layermanager.earth.state.feature);
  var screenPoint = layermanager.earth.state.plugin.getView().project(
      location.latitude, location.longitude, 0,
      layermanager.earth.state.plugin.ALTITUDE_RELATIVE_TO_GROUND);
  jQuery.each(layermanager.earth.registeredSyncers_, function(_, syncer) {
    syncer(screenPoint);
  });
};

/*******************************************************************************
*                                  Utilities                                   *
*******************************************************************************/

/**
 * A simple reusable handler that simply cancels the event passed to it.
 * @param {Object} event The jQuery event to cancel.
 */
layermanager.earth.preventDefault = function(event) {
  event.preventDefault();
};

/**
 * Gets the value of the specified query string parameter.
 * @param {string} name The name of the query parameter to get.
 * @return {?string} The value of the specified query parameter, or null if no
 *     argument with the specified name exists.
 */
layermanager.earth.getQueryArg = function(name) {
  var queryString = window.location.search;
  var regex = new RegExp('[?&]' + name + '=([^&]*)');
  var match = queryString.match(regex);
  if (match) {
    return match[1];
  } else {
    return null;
  }
};

/**
 * Finds the ID of the resource to which a URL points.
 * @param {string} url The resource URL.
 * @return {?string} The numeric ID of the resource, or null if no ID could be
 *     determined.
 */
layermanager.earth.getResourceId = function(url) {
  // Match a resource ID, optionally followed by an extension, which we ignore.
  var match = url.match(/(\d+)(?:\.\w+)?$/);
  if (match) {
    return match[1];
  } else {
    for (var type in layermanager.resources) {
      if (layermanager.resources.hasOwnProperty(type)) {
        var list = layermanager.resources[type];
        if (list[url]) return list[url].id;
      }
    }
    return null;
  }
};

/**
 * Gets the backend-generated URL for a particular resource.
 * @param {string} id The numeric ID of the resource.
 * @return {?string} The resource URL, or null if the resource couldn't be
 *     found.
 */
layermanager.earth.getResolvedResourceUrl = function(id) {
  var url = null;
  jQuery.each(layermanager.resources, function(type, list) {
    jQuery.each(list, function(_, resource) {
      if (resource.id == id) {
        url = resource.url;
        return false;
      }
    });
    if (url) return false;
  });
  return url;
};

/**
 * Converts the specified input fields into color pickers protected by an iframe
 * "shim" that prevents the Earth plugin from being drawn over the color picker
 * popup.
 * @param {Object} inputs A jQuery-wrapped set of <input> elements.
 */
layermanager.earth.initShimmedColorPicker = function(inputs) {
  jQuery(inputs).each(function() {
    var that = this;
    var shim = jQuery('<iframe src="javascript:false;" frameborder="0">');
    shim.appendTo('body');
    shim.css({
      position: 'absolute',
      display: 'none',
      'z-index': 999
    });
    jQuery(this).ColorPicker({
      color: 'ffffffff',
      alpha: true,
      palette: false,
      onShow: function(colorPicker) {
        var jQuerycolorPicker = jQuery(colorPicker);
        jQuerycolorPicker.css('z-index', 1000).show();
        shim.css({
          width: jQuerycolorPicker.width(),
          height: jQuerycolorPicker.height(),
          top: jQuerycolorPicker.position().top,
          left: jQuerycolorPicker.position().left,
          display: 'block'
        });
        return false;
      },
      onHide: function(colorPicker) {
        shim.css({display: 'none'});
      },
      onChange: function(hsb, hex, rgb) {
        var hexMinusAlpha = hex.slice(2);
        jQuery(that).val(hex);
        jQuery(that).css({
          'color': '#' + hexMinusAlpha,
          'background-color': '#' + hexMinusAlpha
        });
      }
    }).attr('spellcheck', 'false').addClass('color-picker').focus(function() {
      jQuery(this).blur();
    });
  });
};

/**
 * Gets the type of a KML Feature object. If it contains a geometry, the type of
 * the geometry is returned instead.
 * @param {KmlFeature} feature The object whose type is to be retrieved.
 * @return {?string} The type of the feature or its geometry, or null if the
 *     feature parameter is falsy.
 */
layermanager.earth.getFeatureType = function(feature) {
  if (feature) {
    if (feature.getGeometry) feature = feature.getGeometry();
    return feature.getType();
  } else {
    return null;
  }
};

/**
 * Strips the leading "Kml" from a feature type.
 * @param {?string} type The type name, with its initial "Kml".
 * @return {?string} The type with the leading "Kml" stripped if it has a "Kml"
 *     prefix, or the input itself otherwise.
 */
layermanager.earth.stripKmlPrefix = function(type) {
  if (type && type.slice(0, 3) == 'Kml') {
    return type.slice(3);
  } else {
    return type;
  }
};

/**
 * Wraps a function, discarding calls to it unless
 * layermanager.earth.CALLBACK_INTERVAL_LIMIT milliseconds have passed since the
 * last call. Useful for preventing heavy event handlers for mousemove/drag
 * events from running too often.
 * @param {function()} callback The function to wrap. The number of parameters
 *     does not matter (whatever arguments are passed will be forwarded).
 * @return {function(...[*])} The wrapped function.
 */
layermanager.earth.limitCallFrequency = function(callback) {
  var lastTime = Date.now();
  return function() {
    var time = Date.now();
    if (time - lastTime > layermanager.earth.CALLBACK_INTERVAL_LIMIT) {
      callback.apply(this, arguments);
      lastTime = time;
    }
  };
};

/**
 * Centers the 3D editor viewport camera on the specified KML feature.
 * @param {Object} kmlObject The KML feature to center on.
 */
layermanager.earth.flyToFeature = function(kmlObject) {
  var bounds = layermanager.earth.state.extensions.dom.computeBounds(kmlObject);
  if (bounds && bounds.getCenter()) {
    layermanager.earth.state.extensions.view.setToBoundsView(bounds, {
      aspectRatio: jQuery('#viewport').width() / jQuery('#viewport').height(),
      defaultRange: layermanager.earth.DEFAULT_RANGE
    });
  }
};

/**
 * Shows an error message box on top of the editing panel.
 * @param {string} message The message to display (may contain HTML).
 */
layermanager.earth.showError = function(message) {
  jQuery('#error').html(message).show();
};

/**
 * Hides the error message box.
 */
layermanager.earth.clearError = function() {
  jQuery('#error').hide();
};

/**
 * Resets the whole geometry editor control to a virgin state, by removing any
 * loaded Earth content, clearing periodically-running functions, and hiding the
 * error message box.
 */
layermanager.earth.resetEditor = function() {
  layermanager.earth.state.extensions.dom.clearFeatures();
  layermanager.earth.clearEarthEvents();
  layermanager.earth.clearSyncers();
  layermanager.earth.clearError();
};

/**
 * Fetches a list of resources for a given layer and fills layermanager.resources
 * with them.
 * @param {(string|number)} layerId the ID of the layer whose resources to load.
 */
layermanager.earth.loadResourcesList = function(layerId) {
  // TODO: Make an alternative to this for huge layers.
  if (layermanager.earth.lastLoadedLayer != layerId) {
    var url = layermanager.earth.RESOURCE_LIST_URL + layerId;
    jQuery.getJSON(url, function(list) {
      jQuery.each(list, function(_, resource) {
        if (resource.type == 'model_in_kmz') resource.type = 'model';
        if (resource.type != 'image' && resource.type != 'icon' &&
            resource.type != 'model') return;
        layermanager.resources[resource.type][resource.url] = resource;
      });
      layermanager.earth.lastLoadedLayer = layerId;
    });
  }
};

/**
 * Convert an altitudeMode from its numeric value used when
 * communicating with the Earth plugin to the string value used when
 * communicating with the layer manager.
 * @param {number} numeric The numeric value of the altitude mode.
 * @return {string} The string representation of the altitude mode.
 */
layermanager.earth.describeAltitudeMode = function(numeric) {
  var plugin = layermanager.earth.state.plugin;
  var lookup = {};
  lookup[plugin.ALTITUDE_CLAMP_TO_GROUND] = 'clampToGround';
  lookup[plugin.ALTITUDE_RELATIVE_TO_GROUND] = 'relativeToGround';
  lookup[plugin.ALTITUDE_ABSOLUTE] = 'absolute';
  lookup[plugin.ALTITUDE_CLAMP_TO_SEA_FLOOR] = 'clampToSeaFloor';
  lookup[plugin.ALTITUDE_RELATIVE_TO_SEA_FLOOR] = 'relativeToSeaFloor';
  return lookup[numeric] || null;
};

/**
 * Convert an altitudeMode from its string value used when communicating
 * with the layer manager to the numeric value used when communicating
 * with the Earth plugin.
 * @param {string} string The string representation of the altitude mode.
 * @return {?number} The numeric value of the altitude mode, or null if an
 *     unknown altitude mode was passed.
 */
layermanager.earth.parseAltitudeMode = function(string) {
  var plugin = layermanager.earth.state.plugin;
  var lookup = {
    clampToGround: plugin.ALTITUDE_CLAMP_TO_GROUND,
    relativeToGround: plugin.ALTITUDE_RELATIVE_TO_GROUND,
    absolute: plugin.ALTITUDE_ABSOLUTE,
    clampToSeaFloor: plugin.ALTITUDE_CLAMP_TO_SEA_FLOOR,
    relativeToSeaFloor: plugin.ALTITUDE_RELATIVE_TO_SEA_FLOOR
  };
  return lookup[string] === undefined ? null : lookup[string];
};

google.setOnLoadCallback(layermanager.earth.initialize);
