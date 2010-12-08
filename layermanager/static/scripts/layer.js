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
 * @fileoverview Event handlers for the layer properties editing page.
 */

layermanager.layer = {};

/**
  * Collects the layer properties from their fields into an object.
  * @return {Object} The collected fields.
  */
layermanager.layer.collectFields = function() {
  return {
    name: jQuery('#name').val(),
    description: jQuery('#description').val(),
    icon: jQuery('#icon').val(),
    world: jQuery('#world').val(),
    item_type: jQuery('#item_type').val(),
    auto_managed: jQuery('#auto_managed').attr('checked') ? '1' : '',
    division_size: jQuery('#division_size').val(),
    division_lod_min: jQuery('#division_lod_min').val(),
    division_lod_min_fade: jQuery('#division_lod_min_fade').val(),
    division_lod_max: jQuery('#division_lod_max').val(),
    division_lod_max_fade: jQuery('#division_lod_max_fade').val(),
    dynamic_balloons: jQuery('#dynamic_balloons').attr('checked') ? '1' : '',
    compressed: jQuery('#compressed').attr('checked') ? '1' : '',
    uncacheable: jQuery('#uncacheable').attr('checked') ? '1' : '',
    custom_kml: jQuery('#custom_kml').val()
  };
};

/**
 * Creates a new layer from the current contents of the layer form.
 */
layermanager.layer.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'layer',
  collect: layermanager.layer.collectFields,
  validate: layermanager.util.validateFieldsContainName,
  succeed: function(id) {
    window.location = '/layer-form/' + id;
  }
});

/**
 * Updates the current layer with the contents of the layer form.
 */
layermanager.layer.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'layer',
  collect: layermanager.layer.collectFields,
  validate: layermanager.util.validateFieldsContainName,
  succeed: function(_, fields) {
    jQuery('#current_layer').text(fields.name);
  }
});

/**
 * Deletes the current layer.
 */
layermanager.layer.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'layer',
  validate: function() {
    return confirm('Are you sure you want to permanently delete this layer? ' +
                    'This operation is irreversible.');
  },
  succeed: function() {
    window.location = '/';
  }
});

/**
  * Updates the visibility of the regionation settings inputs depending on
  * whether the auto_managed checkbox is checked.
  */
layermanager.layer.refreshRegionationVisibility = function() {
  var visible = jQuery('#auto_managed').attr('checked');
  jQuery('#regionation_settings').toggle(visible);
};

/**
 * Initializes event handlers and hides unnecessary buttons.
 */
layermanager.layer.initialize = function() {
  jQuery('#layer_create').click(layermanager.layer.create);
  jQuery('#layer_apply').click(layermanager.layer.update);
  jQuery('#layer_delete').click(layermanager.layer.destroy);
  jQuery('#auto_managed').click(layermanager.layer.refreshRegionationVisibility);

  layermanager.ui.initIntegerField(jQuery('#regionation_settings input'));
  if (layermanager.resources.layer.id) {
    jQuery('#layer_create').hide();
    layermanager.ui.visualizeIconSelect(jQuery('.icon-selector'));
    layermanager.layer.refreshRegionationVisibility();
  } else {
    jQuery('#icon,label[for=icon]').hide();
    jQuery('#layer_apply,#layer_delete').hide();
  }
};

google.setOnLoadCallback(layermanager.layer.initialize);
