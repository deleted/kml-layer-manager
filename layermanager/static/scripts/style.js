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
 * @fileoverview Event handlers for the style editing page.
 */

layermanager.style = {};

/**
  * Collects the values of the style form fields into a single object.
  * @return {Object} A map of field names to their values.
  */
layermanager.style.collectFields = function() {
  var fields = {};
  fields.layer_id = layermanager.resources.layer.id;
  fields.style_id = jQuery('#style_select').val();
  fields.name = jQuery('#style_name').val();
  jQuery('input[type=checkbox][id$=_enable]').each(function() {
    var checked = jQuery(this).is(':checked');
    var field_name = jQuery(this).attr('id').match(/^(.+)_enable$/)[1];
    var field_element = jQuery('#' + field_name);
    if (checked) {
      if (field_element.length) {
        var value = field_element.val();
        if (field_name.match(/_color$/) && value) {
          value = layermanager.format.ARGBToABGRColor(value);
        }
        fields[field_name] = value;
      } else {
        fields[field_name] = '1';
      }
    } else {
      fields[field_name] = '';
    }
  });
  return fields;
};

/** Sends a POST request to create a new style with the values from the form. */
layermanager.style.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'style',
  collect: layermanager.style.collectFields,
  validate: layermanager.style.validateFieldsContainName,
  succeed: function(result, fields) {
    var new_id = parseInt(result);
    layermanager.resources.styles[new_id] = fields;
    layermanager.resources.styles[new_id].id = new_id;
    delete layermanager.resources.styles[new_id].layer_id;
    delete layermanager.resources.styles[new_id].style_id;
    layermanager.style.refreshList();
    jQuery('#style_select').val(new_id);
    layermanager.style.hideForm();
  }
});

/**
  * Sends a POST request to update the selected style with values from the form.
  */
layermanager.style.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'style',
  collect: layermanager.style.collectFields,
  validate: layermanager.style.validateFieldsContainName,
  succeed: function(_, fields) {
    var id = fields.style_id;
    layermanager.resources.styles[id] = fields;
    delete layermanager.resources.styles[id].layer_id;
    delete layermanager.resources.styles[id].style_id;
    layermanager.style.refreshList();
    layermanager.style.hideForm();
  }
});

/** Sends a POST request to delete the selected style. */
layermanager.style.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'style',
  collect: function() {
    return {style_id: jQuery('#style_select').val()};
  },
  succeed: function(_, fields) {
    delete layermanager.resources.styles[fields.style_id];
    layermanager.style.refreshList();
    jQuery('#style_select').val(fields.style_id);
    layermanager.style.hideForm();
  }
});

/** Refills the style selection drop-down from layermanager.resources.styles. */
layermanager.style.refreshList = function() {
  var select = jQuery('#style_select');
  var selected_style = select.val();

  select.html('');

  jQuery.each(layermanager.resources.styles, function(id, style) {
    select.append(jQuery('<option>').text(style.name).attr('value', id));
  });

  if (jQuery('option', select).length == 0) {
    select.append('<option>No styles defined</option>').attr('disabled', true);
    jQuery('#style_edit_button,#style_delete_button').attr('disabled', true);
  } else {
    select.attr('disabled', false);
    jQuery('#style_edit_button,#style_delete_button').attr('disabled', false);
    select.val(selected_style);
  }
};

/**
  * Shows the style form, either empty or filled with values from the style
  * selected in the styles dropdown.
  * @param {string} type The type of form to open. Either "create" to open an
  *     empty one with the "Create" button visible, or "edit" to fill it with
  *     properties of the selected style and show the "Apply" button.
  */
layermanager.style.showForm = function(type) {
  jQuery('#style_form_create').toggle(type == 'create');
  jQuery('#style_form_apply').toggle(type == 'edit');

  // Mark all style properties as unspecified.
  jQuery('#style_form_table td:first-child input')
      .attr('checked', false).change();
  // Replace the values for all style fields with their defaults, or empty
  // strings if they have no default specified.
  jQuery('input,select', '#style_form_table td:last-child').each(function() {
    jQuery(this).val(jQuery(this).attr('data-default') || '');
  }).change();

  if (type == 'edit') {
    var currentStyleId = jQuery('#style_select').val();
    var currentStyle = layermanager.resources.styles[currentStyleId];
    jQuery('#style_name').val(currentStyle.name);
    jQuery.each(currentStyle, function(property, value) {
      if (value || value === 0) {
        if (property.match(/_color$/)) {
          value = layermanager.format.ABGRToARGBColor(value);
          jQuery('#' + property).ColorPickerSetColor(value).css({
            'background-color': '#' + value.slice(2),
            'color': '#' + value.slice(2)
          });
        }
        jQuery('#' + property).val(value).change();
        jQuery('#' + property + '_enable').attr('checked', true).change();
      }
    });
  }
  jQuery('#style_form').show();
};

/** Hides the style form. */
layermanager.style.hideForm = function() {
  jQuery('#style_form').hide();
};

/**
 * Handles the change event of a style property enabled/disabled checkbox,
 * enabling or diabling the controls in the same row as the checkbox. It handles
 * color selectors and sets their color to match the usual enabled/disabled
 * color scheme.
 * @this {Element} The checkbox being handled.
 */
layermanager.style.updateRow = function() {
  var active = jQuery(this).is(':checked');
  var row = jQuery(this).closest('tr');
  row.toggleClass('disabled', !active);
  jQuery('td:last-child>*', row)
      .toggleClass('disabled', !active).attr('disabled', !active);
  var color = active ? 'FFFFFF' : 'E3E3E3';
  if (!active || !jQuery('.color-selector', row).val()) {
    jQuery('.color-selector', row).ColorPickerSetColor('FF' + color).css({
      'background-color': '#' + color,
      'color': '#' + color
    }).val('');
  }
}

/** Initializes the controls and event handlers of the style form. */
layermanager.style.initForm = function() {
  var icon_selects = jQuery('.icon-selector');
  icon_selects.html('<option value="">None</option>');
  jQuery.each(layermanager.resources.icons, function(key, name) {
    icon_selects.append('<option value="' + key + '">' + name + '</option>');
  });
  layermanager.ui.visualizeIconSelect(icon_selects);

  layermanager.ui.initColorPicker(jQuery('.color-selector'));
  layermanager.ui.initIntegerField(jQuery('.integer-field'));
  layermanager.ui.initFloatField(jQuery('.float-field'));

  var checkboxes = jQuery('#style_form_table td:first-child input');
  checkboxes.change(layermanager.style.updateRow).change();

  function toggleHighlight() {
    var active = jQuery(this).is(':checked');
    jQuery(this).closest('tr').nextAll().toggle(active);
  }
  jQuery('#has_highlight_enable').change(toggleHighlight).change();
};

/** Initializes the style dropdown, form, and button event handlers. */
layermanager.style.initialize = function() {
  layermanager.style.refreshList();
  layermanager.style.initForm();

  jQuery('#style_form_create').click(layermanager.style.create);
  jQuery('#style_form_apply').click(layermanager.style.update);
  jQuery('#style_form_cancel').click(layermanager.style.hideForm);
  jQuery('#style_edit_button').click(function() {
    layermanager.style.showForm('edit');
  });
  jQuery('#style_delete_button').click(layermanager.style.destroy);
  jQuery('#style_create_button').click(function() {
    layermanager.style.showForm('create');
  });
  jQuery('#style_select').change(function() {
    if (jQuery('#style_form_apply').is(':visible')) {
      layermanager.style.showForm('edit');
    }
  });
};

google.setOnLoadCallback(layermanager.style.initialize);
