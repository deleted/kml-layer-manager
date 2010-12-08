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
 * @fileoverview Event handlers for the entity editing page.
 */

layermanager.entity = {};

/**
  * The entity being edited.
  * @type Object.<string,Object>
  */
layermanager.entity.currentEntity = {};

/**
  * The index of the geometry being edited in the editor. If the geometry being
  * edited is a new one to be added, the index is null.
  * @type ?number
  */
layermanager.entity.currentGeometryIndex = null;

/**
  * Returns the Earth editor window.
  * @return {Window} The Earth editor global window object.
  */
layermanager.entity.getEditor = function() {
  return jQuery('#earth').get(0).contentWindow;
};

/**
  * Checks whether the editor control is busy (but hasn't failed).
  * @return {boolean} Whether the editor is busy.
  */
layermanager.entity.isEditorBusy = function() {
  var editor = layermanager.entity.getEditor();
  return !(editor.layermanager.earth.api.isLoaded() === false ||
           editor.layermanager.earth.api.isReady());
};

/**
  * Switches the Earth control into the geometry editor mode, optionally loading
  * a particular geometry.
  * @param {Object=} geometry The geometry to edit. If not specified, the user
  *     will be allowed to create a new geometry.
  */
layermanager.entity.showGeometryEditor = function(geometry) {
  var editor = layermanager.entity.getEditor();

  try {
    if (geometry) {
      editor.layermanager.earth.api.loadGeometryForEditing(
          geometry.type, geometry.fields, function() {
        // TODO: Fully support view_is_camera; update earth.api.setView.
        if (jQuery('#view_latitude').val() &&
            jQuery('#view_longitude').val() &&
            jQuery('#view_range').val().val()) {
          editor.layermanager.earth.api.setView(
              parseFloat(jQuery('#view_latitude').val()) || 0,
              parseFloat(jQuery('#view_longitude').val()) || 0,
              parseFloat(jQuery('#view_range').val()) || 0,
              parseFloat(jQuery('#view_altitude').val()) || 0,
              parseFloat(jQuery('#view_heading').val()) || 0,
              parseFloat(jQuery('#view_tilt').val()) || 0);
        }
      });
    } else {
      editor.layermanager.earth.api.startEntityCreation();
    }
  } catch (e) {
    // Plugin not supported or not installed. Can still continue without it.
  }
};

/**
  * Switches the Earth control into entity picking mode, showing all entities.
  */
layermanager.entity.showVisualEntityPicker = function() {
  try {
    layermanager.entity.getEditor().layermanager.earth.api.loadLayerForPicking(
        layermanager.resources.layer.id);
  } catch (e) {
    // Plugin not supported or not installed. Can still continue without it.
  }
};

/**
  * Collects the entity form fields for submission.
  * @return {Object} A map of the collected fields.
  */
layermanager.entity.collectFields = function() {
  var fields = {};
  fields.entity_id = jQuery('#entity_select').val();
  var inputs = jQuery('input[type!=button],select,textarea', '#entity_form');
  inputs.each(function() {
    fields[jQuery(this).attr('id')] = jQuery(this).val();
  });
  if (fields.template) {
    fields.schema = layermanager.resources.templateSchemas[fields.template];
  }
  fields.geometries = JSON.stringify(
    layermanager.entity.currentEntity.geometries);
  return fields;
};

/**
  * Validates that the entity fields contain a name and a geometry and warns the
  * users if they don't.
  * @param {Object} fields A map of the entity fields to validate.
  * @return {boolean} True if validation passes. Undefined otherwise.
  */
layermanager.entity.validate = function(fields) {
  if (!fields.name) {
    layermanager.ui.reportError('An entity must have a non-empty name.');
  } else if (!fields.geometries || fields.geometries == '[]') {
    layermanager.ui.reportError('An entity must have at least one geometry.');
  } else {
    return true;
  }
};

/**
 * Sends a POST request to create a new entity with the values in the form.
 */
layermanager.entity.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'entity',
  collect: layermanager.entity.collectFields,
  validate: layermanager.entity.validate,
  succeed: function(result, fields) {
    var new_id = parseInt(result);
    layermanager.resources.entities[new_id] = fields.name;
    layermanager.entity.refreshEntitiesList();
    if (!layermanager.resources.layer.autoManaged) {
      jQuery('#entity_select').val(new_id);
    }
    layermanager.entity.hideForm();
  }
});

/**
  * Sends a POST request to update the currently selected entity with the
  * values in the form.
  */
layermanager.entity.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'entity',
  collect: layermanager.entity.collectFields,
  validate: layermanager.entity.validate,
  succeed: function(_, fields) {
    var id = fields.entity_id;
    if (fields.name) layermanager.resources.entities[id] = fields.name;
    layermanager.entity.refreshEntitiesList();
    if (!layermanager.resources.layer.autoManaged) {
      jQuery('#entity_select').val(id);
    }
    layermanager.entity.hideForm();
  }
});

/**
 * Sends a POST request to delete the currently selected entity.
 */
layermanager.entity.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'entity',
  collect: function(id) {
    return {entity_id: jQuery('#entity_select').val()};
  },
  succeed: function(_, fields) {
    delete layermanager.resources.entities[fields.entity_id];
    layermanager.entity.refreshEntitiesList();
    layermanager.entity.hideForm();
  }
});

/**
 * Fills the styles dropdown from layermanager.resources.styles.
 */
layermanager.entity.fillStylesList = function() {
  var styleSelect = jQuery('#style');
  styleSelect.html('<option value="">None</option>');
  jQuery.each(layermanager.resources.styles, function(id, name) {
    styleSelect.append('<option value="' + id + '">' + name + '</option>');
  });
};

/**
 * Fills the regions dropdown from layermanager.resources.regions.
 */
layermanager.entity.fillRegionsList = function() {
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

/**
 * Fills the templates dropdown from layermanager.resources.schemas.
 */
layermanager.entity.fillTemplatesList = function() {
  var templateSelect = jQuery('#template');
  templateSelect.html('<option value="">None</option>');
  jQuery.each(layermanager.resources.schemas, function(id, schema) {
    templateSelect.append('<optgroup label="' + schema.name + '">');
    jQuery.each(schema.templates, function(id, name) {
      var option = jQuery('<option value="' + id + '">');
      templateSelect.append(option.html('&nbsp;&nbsp;' + name));
    });
    templateSelect.append('</optgroup>');
  });
};

/**
 * Fills the entities drop-down from layermanager.resources.entities.
 */
layermanager.entity.refreshEntitiesList = function() {
  if (!layermanager.resources.layer.autoManaged) {
    var select = jQuery('#entity_select');

    select.html('');

    jQuery.each(layermanager.resources.entities, function(id, entity) {
      select.append(jQuery('<option>').text(entity).attr('value', id));
    });

    var listEmpty = (jQuery('option', select).length == 0);
    if (listEmpty) select.append('<option>No entities defined</option>');
    select.attr('disabled', listEmpty);
    jQuery('#entity_edit_button,#entity_delete_button')
        .attr('disabled', listEmpty);
  }
};

/**
  * Displays the entity form and geometry editor, optionally filling if with
  * values from the selected entity.
  * @param {string} type Either "create" to show an empty form and switch the
  *     geometry editor to creation mode, or "edit" to fill the form with values
  *     from the selected entity and load its first geometry into the editor.
  */
layermanager.entity.showForm = function(type) {
  function actuallyShowForm(entity) {
    jQuery('#entity_form_create').toggle(type == 'create');
    jQuery('#entity_form_apply').toggle(type == 'edit');
    jQuery('input[type!=button],select,textarea', '#entity_form')
        .val('').change();
    if (entity) {
      jQuery.each(entity, function(key, value) {
        jQuery('#' + key).val(value || '').change();
      });
      layermanager.entity.currentEntity = entity;
      layermanager.entity.currentGeometryIndex = 0;
      layermanager.entity.showGeometryEditor(entity.geometries[0]);
    } else {
      layermanager.entity.currentEntity = {'geometries': []};
      layermanager.entity.currentGeometryIndex = null;
      layermanager.entity.showGeometryEditor();
    }
    layermanager.entity.refreshViewpointDescription();
    layermanager.entity.refreshGeometryDescription();
    jQuery('#entity_form').show();
  }

  if (!layermanager.entity.isEditorBusy()) {
    if (type == 'edit') {
      var id = jQuery('#entity_select').val();
      var url = '/entity-raw/' + layermanager.resources.layer.id + '?id=' + id;
      jQuery.get(url, function(entity) {
        entity = JSON.parse(entity);
        entity.geometries = jQuery.map(entity.geometries, function(geometry) {
          return {type: geometry.type, fields: geometry};
        });
        if (entity.view_location) {
          entity.view_latitude = entity.view_location[0];
          entity.view_longitude = entity.view_location[1];
        }
        actuallyShowForm(entity);
      });
    } else {
      actuallyShowForm(null);
    }
  }
};

/**
 * Hides the entity form and switches the Earth control to the picking mode.
 */
layermanager.entity.hideForm = function() {
  if (!layermanager.entity.isEditorBusy()) {
    layermanager.entity.showVisualEntityPicker();
    jQuery('#entity_form').hide();
  }
};

/**
  * Refreshes the list of schema fields in the form with ones used by the
  * currently selected template.
  */
layermanager.entity.updateSchemaFields = function() {
  var fieldsDiv = jQuery('#schema_fields');
  fieldsDiv.html('');
  var templateId = jQuery('#template').val();
  if (templateId) {
    var schemaId = layermanager.resources.templateSchemas[templateId];
    var fields = layermanager.resources.schemas[schemaId].fields;
    jQuery.each(fields, function(_, field) {
      var fieldName = 'field_' + field.name;
      jQuery('<label>').attr({
        'for': fieldName,
        title: field.tip
      }).text(field.name + ':').appendTo(fieldsDiv);
      if (field.type == 'text') {
        var fieldInput = jQuery('<textarea>');
      } else if (!layermanager.resources.layer.autoManaged &&
                 (field.type == 'image' || field.type == 'icon' ||
                  field.type == 'resource')) {
        if (field.type == 'image') {
          var source = layermanager.resources.images;
        } else if (field.type == 'icon') {
          var source = layermanager.resources.icon;
        } else {
          var source = layermanager.resources.other;
        }
        var fieldInput = jQuery('<select>');
        fieldInput.append(jQuery('<option value="">None</option>'));
        jQuery.each(source, function(id, name) {
          fieldInput.append(jQuery('<option value="' + id + '">').text(name));
        });
      } else {
        var fieldInput = jQuery('<input type="text">');
      }
      fieldInput.attr({
        id: fieldName,
        title: field.tip,
        'class': 'field-' + field.type
      }).appendTo(fieldsDiv);
      if (layermanager.entity.currentEntity[fieldname] !== undefined) {
        fieldInput.val(layermanager.entity.currentEntity[fieldName]);
      }
    });
    if (!layermanager.resources.layer.autoManaged) {
      layermanager.ui.visualizeImageSelect(jQuery('.field-image', fieldsDiv));
      layermanager.ui.visualizeIconSelect(jQuery('.field-icon', fieldsDiv));
    }
    layermanager.ui.initColorPicker(jQuery('.field-color', fieldsDiv), true);
    layermanager.ui.initIntegerField(jQuery('.field-integer', fieldsDiv));
    layermanager.ui.initFloatField(jQuery('.field-float', fieldsDiv));
    layermanager.ui.initDateField(jQuery('.field-date', fieldsDiv));
  }
  var toggler = jQuery(fieldsDiv).prev('.toggler');
  toggler.toggleClass('untoggleable', !(templateId && fields));
};

/**
  * Refreshes the viewpoint description message based on the viewpoint values
  * in the hidden form fields.
  */
layermanager.entity.refreshViewpointDescription = function() {
  var message;
  // TODO: Support view_is_camera.
  if (jQuery('#view_latitude').val() && jQuery('#view_longitude').val() &&
      jQuery('#view_range').val()) {
    var template = 'Looking at <b>$lat, $lon</b> from <b>$range</b> away.';
    var latitude = layermanager.format.formatLatitude(
        jQuery('#view_latitude').val());
    var longitude = layermanager.format.formatLongitude(
        jQuery('#view_longitude').val());
    var range = layermanager.format.formatAltitude(
        jQuery('#view_range').val());
    message = template.replace('$lat', latitude)
                      .replace('$lon', longitude)
                      .replace('$range', range);
    jQuery('#view_clear').show();
  } else {
    message = 'None';
    jQuery('#view_clear').hide();
  }
  jQuery('#viewport_summary').html(message);
};

/**
  * Refreshes the geometry description message based on the geometry type
  * currently in the hidden form fields.
  */
layermanager.entity.refreshGeometryDescription = function() {
  var summary = jQuery('#geometry_summary');
  if (layermanager.entity.currentEntity.geometries.length == 0) {
    summary.html('None');
    return;
  }

  summary.html('');
  jQuery.each(layermanager.entity.currentEntity.geometries,
              function(index, geometry) {
    var type = geometry.type.replace(/([a-z])([A-Z])/g, '$1 $2');
    var typeLabel = jQuery('<span class="geometry-type"></span>').text(type);
    var editIcon = jQuery('<img src="/static/img/edit.png" />');
    var deleteIcon = jQuery('<img src="/static/img/delete.png" />');
    var record = jQuery('<span class="geometry-record"></span>');
    record.append(typeLabel, editIcon, deleteIcon).appendTo(summary);

    if (index == layermanager.entity.currentGeometryIndex) {
      record.addClass('currently-edited');
    }

    deleteIcon.click(function() {
      var currentGeometries = layermanager.entity.currentEntity.geometries;
      var currentIndex = currentGeometries.indexOf(geometry);
      if (currentIndex == layermanager.entity.currentGeometryIndex) {
        layermanager.entity.currentGeometryIndex = null;
        layermanager.entity.showGeometryEditor();
      }
      layermanager.entity.currentEntity.geometries.splice(currentIndex, 1);
      layermanager.entity.refreshGeometryDescription();
    });

    editIcon.click(function() {
      var currentGeometries = layermanager.entity.currentEntity.geometries;
      var currentIndex = currentGeometries.indexOf(geometry);
      layermanager.entity.currentGeometryIndex = currentIndex;
      layermanager.entity.showGeometryEditor(geometry);
      layermanager.entity.refreshGeometryDescription();
    });
  });
};

/**
  * Receives a new geometry description from the Earth control, sets the
  * relevant form fields for it, and updates the geometry description, turning
  * it temporarily to maroon to alert the user to the change being acknowledged.
  * @param {string} type The type of the new geometry.
  * @param {Object} details A map of properties of the new geometry.
  */
layermanager.entity.receiveGeometry = function(type, details) {
  if (layermanager.entity.currentGeometryIndex === null) {
    layermanager.entity.currentGeometryIndex =
        layermanager.entity.currentEntity.geometries.length;
    layermanager.entity.currentEntity.geometries.push({
      type: type, fields: details
    });
    layermanager.entity.refreshGeometryDescription();
  } else {
    var index = layermanager.entity.currentGeometryIndex;
    layermanager.entity.currentEntity.geometries[index] =
        {type: type, fields: details};
    jQuery('.currently-edited').animate({
      left: '+=0'  // Dummy to make sure the step function is called.
    }, {
      duration: 1000,
      step: function(_, fx) {
        var red = Math.round((0xA7 * (1 - fx.pos)));
        jQuery(this).css('color', 'rgb(' + red + ', 0, 0)');
      }
    });
  }
};

/**
  * Makes the Earth control resizeable and binds handlers for its events that
  * handle entities being picked and the geometry and viewpoint being set.
  * @param {Window} editor The global window object of the Earth control iframe.
  */
layermanager.entity.initEditorEvents = function(editor) {
  editor.layermanager.earth.api.makeResizable(jQuery('#earth'));
  editor.layermanager.earth.api.reportEntityPicked = function(id) {
    jQuery('#entity_select').val(id);
    layermanager.entity.showForm('edit');
  };
  editor.layermanager.earth.api.reportViewSet = function(viewpoint) {
    jQuery.each(viewpoint, function(name, value) {
      jQuery('#' + name).val(value);
    });
    jQuery('#view_is_camera').val('');
    layermanager.entity.refreshViewpointDescription();
  };
  editor.layermanager.earth.api.reportGeometrySet =
      layermanager.entity.receiveGeometry;
};

/**
 * Deletes the saved view settings.
 */
layermanager.entity.clearView = function() {
  jQuery('#view_latitude,#view_longitude,#view_altitude,#view_heading,' +
         '#view_tilt,#view_range,#view_roll,#view_is_camera').val('');
  layermanager.entity.refreshViewpointDescription();
};

/**
  * Initializes the form, fills dropdowns, sets up the Earth control
  * (geometry editor) and binds event handlers to the form buttons.
  */
layermanager.entity.initialize = function() {
  layermanager.entity.fillStylesList();
  layermanager.entity.fillTemplatesList();
  layermanager.entity.fillRegionsList();
  layermanager.entity.refreshEntitiesList();
  layermanager.ui.setupTogglers();
  layermanager.ui.initFloatField(jQuery('#priority'));

  jQuery('#entity_form_create').click(layermanager.entity.create);
  jQuery('#entity_form_apply').click(layermanager.entity.update);
  jQuery('#entity_form_cancel').click(layermanager.entity.hideForm);
  jQuery('#entity_edit_button').click(function() {
    layermanager.entity.showForm('edit');
  });
  jQuery('#entity_delete_button').click(layermanager.entity.destroy);
  jQuery('#entity_create_button').click(function() {
    layermanager.entity.showForm('create');
  });
  jQuery('#template').change(layermanager.entity.updateSchemaFields);
  jQuery('#entity_select').change(function() {
    if (jQuery('#entity_form_apply').is(':visible')) {
      layermanager.entity.showForm('edit');
    }
  });
  jQuery('#view_clear').click(layermanager.entity.clearView);

  jQuery('#geometry_create').click(function() {
    layermanager.entity.currentGeometryIndex = null;
    layermanager.entity.showGeometryEditor();
    layermanager.entity.refreshGeometryDescription();
  });

  var editor = layermanager.entity.getEditor();
  editor.jQuery(function() {
    jQuery(editor.document).ready(function() {
      layermanager.entity.initEditorEvents(editor);
    });
  });
};

google.setOnLoadCallback(layermanager.entity.initialize);
