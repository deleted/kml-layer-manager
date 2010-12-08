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
 * @fileoverview Event handlers for the link editing page.
 */

layermanager.link = {};

/**
  * Collects the values of the link form fields into a single object.
  * @return {Object} A map of field names to their values.
  */
layermanager.link.collectFields = function() {
  return {
    link_id: jQuery('#link_select').val(),
    name: jQuery('#name').val(),
    url: jQuery('#url').val(),
    description: jQuery('#description').val(),
    icon: jQuery('#icon').val(),
    region: jQuery('#region').val(),
    item_type: jQuery('#item_type').val(),
    custom_kml: jQuery('#custom_kml').val()
  };
};

/**
  * Check whether the supplied link fields have a name and a URL.
  * @param {Object} fields The link's fields.
  * @return {boolean} Whether the link has non-empty name and URL.
  */
layermanager.link.validate = function(fields) {
  if (!fields.name) {
    layermanager.ui.reportError('Name cannot be empty!');
  } else if (!fields.url) {
    layermanager.ui.reportError('URL cannot be empty!');
  } else {
    return true;
  }
};

/** Sends a POST request to create a new link with the values from the form. */
layermanager.link.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'link',
  collect: layermanager.link.collectFields,
  validate: layermanager.link.validate,
  succeed: function(result, fields) {
    var new_id = parseInt(result, 10);
    layermanager.resources.links[new_id] = fields;
    layermanager.resources.links[new_id].id = new_id;
    delete layermanager.resources.links[new_id].layer_id;
    delete layermanager.resources.links[new_id].link_id;
    layermanager.link.refreshList();
    jQuery('#link_select').val(new_id);
    layermanager.link.hideForm();
  }
});

/**
  * Sends a POST request to update the selected link with values from the form.
  */
layermanager.link.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'link',
  collect: layermanager.link.collectFields,
  validate: layermanager.link.validate,
  succeed: function(_, fields) {
    var id = fields.link_id;
    layermanager.resources.links[id] = fields;
    delete layermanager.resources.links[id].layer_id;
    delete layermanager.resources.links[id].link_id;
    layermanager.link.refreshList();
    layermanager.link.hideForm();
  }
});

/** Sends a POST request to delete the selected link. */
layermanager.link.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'link',
  collect: function() {
    return {link_id: jQuery('#link_select').val()};
  },
  succeed: function(_, fields) {
    delete layermanager.resources.links[fields.link_id];
    layermanager.link.refreshList();
    jQuery('#link_select').val(fields.link_id);
    layermanager.link.hideForm();
  }
});

/** Refills the link selection drop-down from layermanager.resources.links. */
layermanager.link.refreshList = function() {
  var select = jQuery('#link_select');

  select.html('');

  jQuery.each(layermanager.resources.links, function(id, link) {
    select.append(jQuery('<option>').text(link.name).attr('value', id));
  });

  if (jQuery('option', select).length == 0) {
    select.append('<option>No links defined</option>').attr('disabled', true);
    jQuery('#link_edit_button,#link_delete_button').attr('disabled', true);
  } else {
    select.attr('disabled', false);
    jQuery('#link_edit_button,#link_delete_button').attr('disabled', false);
  }
};

/**
  * Shows the link form, either empty or filled with values from the link
  * selected in the links dropdown.
  * @param {string} type The type of form to open. Either "create" to open an
  *     empty one with the "Create" button visible, or "edit" to fill it with
  *     properties of the selected link and show the "Apply" button.
  */
layermanager.link.showForm = function(type) {
  jQuery('#link_form_create').toggle(type == 'create');
  jQuery('#link_form_apply').toggle(type == 'edit');
  jQuery('input[type!=button],select,textarea', '#link_form').val('').change();

  if (type == 'edit') {
    var currentLinkId = jQuery('#link_select').val();
    jQuery.each(layermanager.resources.links[currentLinkId], function(key, value) {
      jQuery('#' + key).val(value || '').change();
    });
  }
  jQuery('#link_form').show();
};

/** Hides the link form. */
layermanager.link.hideForm = function() {
  jQuery('#link_form').hide();
};

/** Fills the regions drop-down with values from layermanager.resources.regions. */
layermanager.link.fillRegionsList = function() {
  var regionSelect = jQuery('#region');
  regionSelect.html('<option value="">None</option>');
  jQuery.each(layermanager.resources.regions, function(id, region) {
    if (region.name) {
      var label = region.name;
    } else {
      var box = region.coordinates;
      var label = layermanager.format.formatLatitude(box[0]) + ', ' +
                  layermanager.format.formatLongitude(box[1]) + ' to ' +
                  layermanager.format.formatLatitude(box[2]) + ', ' +
                  layermanager.format.formatLongitude(box[3]);
    }
    regionSelect.append('<option value="' + id + '">' + label + '</option>');
  });
};

/** Initializes the link dropdown, form, and button event handlers. */
layermanager.link.initialize = function() {
  layermanager.link.fillRegionsList();
  layermanager.link.refreshList();
  layermanager.ui.visualizeIconSelect(jQuery('#icon'));

  jQuery('#link_form_create').click(layermanager.link.create);
  jQuery('#link_form_apply').click(layermanager.link.update);
  jQuery('#link_form_cancel').click(layermanager.link.hideForm);
  jQuery('#link_delete_button').click(layermanager.link.destroy);
  jQuery('#link_edit_button').click(function() {
    layermanager.link.showForm('edit');
  });
  jQuery('#link_create_button').click(function(){
    layermanager.link.showForm('create');
  });
  jQuery('#link_select').change(function() {
    if (jQuery('#link_form_apply').is(':visible')) {
      layermanager.link.showForm('edit');
    }
  });
};

google.setOnLoadCallback(layermanager.link.initialize);
