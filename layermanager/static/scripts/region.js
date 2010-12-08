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
 * @fileoverview Event handlers for the region editing page.
 */

layermanager.region = {};

/** Resets the editor into its initial state with no regions displayed. */
layermanager.region.clearEditor = function() {
  try {
    jQuery('#earth').get(0).contentWindow.layermanager.earth.api.clear();
  } catch (e) {
    // Plugin not supported or not installed. Can still continue without it.
  }
};

/**
  * Display a region in the editor with properties filled from the form.
  * @param {boolean} flyToRegion If set to true, the viewpoint is moved such
  *     that it shows the whole region.
  */
layermanager.region.showEditor = function(flyToRegion) {
  var editor = jQuery('#earth').get(0).contentWindow;
  var argNames = ['north', 'south', 'east', 'west', 'max_altitude'];
  var args = jQuery.map(argNames, function(arg) {
    return parseFloat(jQuery('#' + arg).val()) || 0;
  });
  args.push(jQuery('#altitude_mode').val());
  args.push(flyToRegion);
  try {
    editor.layermanager.earth.api.loadRegionForEditing.apply(editor, args);
  } catch (e) {
    // Plugin not supported or not installed. Can still continue without it.
  }
};

/**
  * Makes the editor resizeable and initializes a handler that replicates
  * the changes that occur in the editor to the form.
  * @param {Window} editor The global window object of the editor's iframe.
  */
layermanager.region.initEditorEvents = function(editor) {
  editor.layermanager.earth.api.makeResizable(jQuery('#earth'));
  editor.layermanager.earth.api.reportRegionChanged =
      function(north, south, east, west, altitude) {
    jQuery('#north').val(north);
    jQuery('#south').val(south);
    jQuery('#east').val(east);
    jQuery('#west').val(west);
    jQuery('#max_altitude').val(altitude);
  };
  layermanager.region.editorInitialized = true;
};

/**
  * Collects the entity form fields for submission.
  * @return {Object} A map of the collected fields.
  */
layermanager.region.collectFields = function() {
  var fields = {};
  fields.region_id = jQuery('#region_select').val();
  jQuery('input[type!=button],select', '#region_form').each(function() {
    fields[jQuery(this).attr('id')] = jQuery(this).val();
  });
  return fields;
};

/**
  * Validates that the supplied region fields are valid and warns the user if
  * they aren't.
  * @param {Object} fields A map of the region's fields.
  * @return {boolean} True if the fields are valid. Undefined otherwise.
  */
layermanager.region.validate = function(fields) {
  var north = parseFloat(fields.north);
  var south = parseFloat(fields.south);
  var east = parseFloat(fields.east);
  var west = parseFloat(fields.west);
  var min_altitude = parseFloat(fields.min_altitude || 0);
  var max_altitude = parseFloat(fields.max_altitude || 0);
  var min_lod = parseFloat(fields.min_lod || 0);
  var max_lod = parseFloat(fields.max_lod || 0);
  if (!(fields.north && fields.south && fields.east && fields.west)) {
    // The above check is done on the unparsed strings, so '0' passes through.
    layermanager.ui.reportError('A region must have its corners defined.');
  } else if (Math.abs(north) > 90 || Math.abs(south) > 90) {
    layermanager.ui.reportError('North and south must be between -90 and +90 ' +
                                'degrees.');
  } else if (north < south) {
    layermanager.ui.reportError('The northern boundary of the region cannot ' +
                                'have lower latitude than the southern.');
  } else if (east < west) {
    layermanager.ui.reportError('The eastern boundary of the region cannot ' +
                                'have lower longitude than the western.');
  } else if (min_altitude > max_altitude) {
    layermanager.ui.reportError('The minimum altitude cannot be higher than the ' +
                                'maximum altitude.');
  } else if (min_lod > max_lod) {
    layermanager.ui.reportError('The minimum LOD cannot be higher than the ' +
                                'maximum LOD.');
  } else {
    return true;
  }
};

/**
  * Sends a POST request to create a region from the current values of the form
  * fields.
  */
layermanager.region.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'region',
  collect: layermanager.region.collectFields,
  validate: layermanager.region.validate,
  succeed: function(result, fields) {
    var new_id = parseInt(result);
    layermanager.resources.regions[new_id] = fields;
    delete layermanager.resources.regions[new_id].layer_id;
    delete layermanager.resources.regions[new_id].region_id;
    layermanager.region.refreshList();
    jQuery('#region_select').val(new_id);
    layermanager.region.hideForm();
  }
});

/**
  * Sends a POST request to update the selected region with the current values
  * of the form fields.
  */
layermanager.region.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'region',
  collect: layermanager.region.collectFields,
  validate: layermanager.region.validate,
  succeed: function(_, fields) {
    var id = fields.region_id;
    jQuery.extend(layermanager.resources.regions[id], fields);
    delete layermanager.resources.regions[id].layer_id;
    delete layermanager.resources.regions[id].region_id;
    layermanager.region.refreshList();
    jQuery('#region_select').val(id);
    layermanager.region.hideForm();
  }
});

/** Sends a POST request to delete the selected region. */
layermanager.region.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'region',
  collect: function() {
    return {region_id: jQuery('#region_select').val()};
  },
  succeed: function(_, fields) {
    delete layermanager.resources.regions[fields.region_id];
    layermanager.region.refreshList();
    layermanager.region.hideForm();
  }
});

/** Fills the regions drop-down from layermanager.resources.regions. */
layermanager.region.refreshList = function() {
  var select = jQuery('#region_select');

  select.html('');

  jQuery.each(layermanager.resources.regions, function(id, region) {
    if (region.name) {
      var label = region.name;
    } else {
      var label = layermanager.format.formatLatitude(region.north) + ', ' +
                  layermanager.format.formatLongitude(region.east) + ' to ' +
                  layermanager.format.formatLatitude(region.south) + ', ' +
                  layermanager.format.formatLongitude(region.west);
    }
    select.append(jQuery('<option>').html(label).attr('value', id));
  });

  var selectEmpty = (jQuery('option', select).length == 0);
  if (selectEmpty) select.append('<option>No regions defined</option>');
  select.attr('disabled', selectEmpty);
  jQuery('#region_edit_button,#region_delete_button')
      .attr('disabled', selectEmpty);
};

/**
  * Displays the region form, either empty or filled with values from the region
  * selected in the dropdown.
  * @param {string} type Either "create" for an empty form, or "edit" to fill it
  *     with the properties of the selected region.
  */
layermanager.region.showForm = function(type) {
  jQuery('#north,#south,#east,#west,#max_altitude,#altitude_mode')
      .unbind('change');
  jQuery('#region_form_create').toggle(type == 'create');
  jQuery('#region_form_apply').toggle(type == 'edit');
  jQuery('input[type!=button],select', '#region_form').val('').change();
  if (type == 'edit') {
    var currentRegionId = jQuery('#region_select').val();
    var currentRegion = layermanager.resources.regions[currentRegionId];
    jQuery.each(currentRegion, function(key, value) {
      jQuery('#' + key).val(typeof value == 'null' ? '' : value);
    });
    if (!jQuery('#altitude_mode').val()) {
      jQuery('#altitude_mode').val('relativeToGround');
    }
  } else {
    jQuery('#altitude_mode').val('relativeToGround');
    jQuery('#north').val('1');
    jQuery('#south').val('-1');
    jQuery('#east').val('1');
    jQuery('#west').val('-1');
  }
  layermanager.region.showEditor(true);
  var fields = jQuery('#north,#south,#east,#west,#max_altitude,#altitude_mode');
  fields.change(function() {
    layermanager.region.showEditor(false);
  });
  jQuery('#region_form').show();
};

/** Hides the region form and resets the editor. */
layermanager.region.hideForm = function() {
  layermanager.region.clearEditor();
  jQuery('#region_form').hide();
  jQuery('#north,#south,#east,#west,#max_altitude,#altitude_mode')
      .unbind('change');
};

/** Initializes the dropdown, form and editor and binds buttons' events. */
layermanager.region.initialize = function() {
  layermanager.region.refreshList();
  layermanager.ui.initFloatField(jQuery('.float-field'), true);

  jQuery('#region_form_create').click(layermanager.region.create);
  jQuery('#region_form_apply').click(layermanager.region.update);
  jQuery('#region_form_cancel').click(layermanager.region.hideForm);
  jQuery('#region_edit_button').click(function() {
    layermanager.region.showForm('edit');
  });
  jQuery('#region_delete_button').click(layermanager.region.destroy);
  jQuery('#region_create_button').click(function() {
    layermanager.region.showForm('create');
  });
  jQuery('#region_select').change(function() {
    if (jQuery('#region_form_apply').is(':visible')) {
      layermanager.region.showForm('edit');
    }
  });

  var editor = jQuery('#earth').get(0).contentWindow;
  editor.jQuery(function() {
    jQuery(editor.document).ready(function() {
      layermanager.region.initEditorEvents(editor);
    });
  });
};

google.setOnLoadCallback(layermanager.region.initialize);
