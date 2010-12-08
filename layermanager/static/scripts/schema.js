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
 * @fileoverview Event handlers for the schema editing page.
 */

/*******************************************************************************
*                                   Schemas                                    *
*******************************************************************************/

layermanager.schema = {};

/**
  * Refills the schemas dropdown with schema id/name pairs from
  * layermanager.resources.schemas.
  */
layermanager.schema.refreshList = function() {
  var select = jQuery('#schema_select');
  var selected_value = select.val();

  select.html('');

  jQuery.each(layermanager.resources.schemas, function(id, schema) {
    select.append(jQuery('<option>').text(schema.name).attr('value', id));
  });

  if (jQuery('option', select).length == 0) {
    select.append('<option>No schemas defined</option>').attr('disabled', true);
    jQuery('#schema_edit_button,#schema_delete_button').attr('disabled', true);
  } else {
    select.attr('disabled', false);
    jQuery('#schema_edit_button,#schema_delete_button').attr('disabled', false);
    select.val(selected_value);
  }
};

/**
  * Shows the schema form, either empty or filled with values from the schema
  * selected in the schemas dropdown.
  * @param {string} type The type of form to open. Either "create" to open an
  *     empty one with the "Create" button visible, or "edit" to fill it with
  *     the name of the selected schema and show the "Apply" button.
  */
layermanager.schema.showForm = function(type) {
  jQuery('#schema_form_create').toggle(type == 'create');
  jQuery('#schema_form_apply').toggle(type == 'edit');
  if (type == 'create') {
    jQuery('.toggler').addClass('untoggleable').removeClass('toggled');
    jQuery('.togglee').hide();
    jQuery('#schema_name').val('');
  } else if (type == 'edit') {
    jQuery('.toggler').removeClass('untoggleable');
    var id = jQuery('#schema_select').val();
    jQuery('#schema_name').val(layermanager.resources.schemas[id].name);
    layermanager.template.refreshList();
    layermanager.template.hideForm();
    layermanager.field.refreshList();
    layermanager.field.hideForm();
  }
  jQuery('#schema_form').show();
};

/** Hides the schema form. */
layermanager.schema.hideForm = function() {
  jQuery('#schema_form').hide();
};

/** Sends a POST request to create a new schema with the name from the form. */
layermanager.schema.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'schema',
  collect: function() {
    return {name: jQuery('#schema_name').val()};
  },
  validate: layermanager.util.validateFieldsContainName,
  succeed: function(result, fields) {
    layermanager.resources.schemas[result] = {
      name: fields.name,
      templates: {},
      fields: {}
    };
    layermanager.schema.refreshList();
    jQuery('#schema_select').val(result);
    layermanager.schema.hideForm();
  }
});

/**
  * Sends a POST request to update the selected schema with name from the form.
  */
layermanager.schema.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'schema',
  collect: function() {
    return {
      schema_id: jQuery('#schema_select').val(),
      name: jQuery('#schema_name').val()
    };
  },
  validate: layermanager.util.validateFieldsContainName,
  succeed: function(_, fields) {
    layermanager.resources.schemas[fields.schema_id].name = fields.name;
    layermanager.schema.refreshList();
    layermanager.schema.hideForm();
  }
});

/** Sends a POST request to delete the selected schema. */
layermanager.schema.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'schema',
  collect: function() {
    return {schema_id: jQuery('#schema_select').val()};
  },
  succeed: function(_, fields) {
    delete layermanager.resources.schemas[fields.schema_id];
    layermanager.schema.refreshList();
    layermanager.schema.hideForm();
  }
});

/** Initializes the schema editor form and buttons with event handlers. */
layermanager.schema.initializeEditor = function() {
  jQuery('#schema_form_create').click(layermanager.schema.create);
  jQuery('#schema_form_apply').click(layermanager.schema.update);
  jQuery('#schema_form_cancel').click(layermanager.schema.hideForm);

  jQuery('#schema_edit_button').click(function() {
    layermanager.schema.showForm('edit');
  });
  jQuery('#schema_delete_button').click(layermanager.schema.destroy);
  jQuery('#schema_create_button').click(function() {
    layermanager.schema.showForm('create');
  });

  jQuery('#schema_select').change(function() {
    if (jQuery('#schema_form_apply').is(':visible')) {
      layermanager.schema.showForm('edit');
    }
  });
};

/*******************************************************************************
*                                  Templates                                   *
*******************************************************************************/

layermanager.template = {};

/**
  * Refills the templates dropdown with template id/name pairs of the selected
  * schema from the schemaList global vairable.
  */
layermanager.template.refreshList = function() {
  var select = jQuery('#template_select');
  var schemaId = jQuery('#schema_select').val();
  var templateList = layermanager.resources.schemas[schemaId].templates;

  select.html('');

  jQuery.each(templateList, function(id, template) {
    select.append(jQuery('<option>').text(template.name).attr('value', id));
  });

  if (jQuery('option', select).length == 0) {
    select.append('<option>No templates defined</option>')
        .attr('disabled', true);
    jQuery('#template_edit_button,#template_delete_button')
        .attr('disabled', true);
  } else {
    select.attr('disabled', false);
    jQuery('#template_edit_button,#template_delete_button')
        .attr('disabled', false);
  }
};

/**
  * Shows the template form, either empty or filled with values from the
  * template selected in the templates dropdown.
  * @param {string} type The type of form to open. Either "create" to open an
  *     empty one with the "Create" button visible, or "edit" to fill it with
  *     the name and text of the selected template and show the "Apply" button.
  */
layermanager.template.showForm = function(type) {
  jQuery('#template_form_create').toggle(type == 'create');
  jQuery('#template_form_apply').toggle(type == 'edit');
  if (type == 'create') {
    jQuery('#template_name,#template_text').val('');
  } else if (type == 'edit') {
    var schemaId = jQuery('#schema_select').val();
    var templateList = layermanager.resources.schemas[schemaId].templates;
    var id = jQuery('#template_select').val();
    jQuery('#template_name').val(templateList[id].name);
    jQuery('#template_text').val(templateList[id].text);
  }
  jQuery('#template_form').show();
};

/** Hides the template form. */
layermanager.template.hideForm = function() {
  jQuery('#template_form').hide();
};

/**
  * Sends a POST request to create a new template with the values from the form.
  */
layermanager.template.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'template',
  collect: function() {
    return {
      schema_id: jQuery('#schema_select').val(),
      name: jQuery('#template_name').val(),
      text: jQuery('#template_text').val()
    };
  },
  validate: layermanager.util.validateFieldsContainName,
  succeed: function(result, fields) {
    layermanager.resources.schemas[fields.schema_id].templates[result] = {
      name: fields.name,
      text: fields.text
    };
    layermanager.template.refreshList();
    jQuery('#template_select').val(result);
    layermanager.template.hideForm();
  }
});

/**
  * Sends a POST request to update the selected template with values from the
  * form.
  */
layermanager.template.update = layermanager.util.makeHandler({
  action: 'update',
  type: 'template',
  collect: function() {
    return {
      schema_id: jQuery('#schema_select').val(),
      template_id: jQuery('#template_select').val(),
      name: jQuery('#template_name').val(),
      text: jQuery('#template_text').val()
    };
  },
  validate: layermanager.util.validateFieldsContainName,
  succeed: function(_, fields) {
    var schemaId = jQuery('#schema_select').val();
    var templateList = layermanager.resources.schemas[schemaId].templates;
    templateList[fields.template_id] = fields;
    layermanager.template.refreshList();
    layermanager.template.hideForm();
  }
});

/** Sends a POST request to delete the selected template. */
layermanager.template.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'template',
  collect: function() {
    return {
      schema_id: jQuery('#schema_select').val(),
      template_id: jQuery('#template_select').val()
    };
  },
  succeed: function(_, fields) {
    var templateList = layermanager.resources.schemas[fields.schema_id].templates;
    delete templateList[fields.template_id];
    layermanager.template.refreshList();
    layermanager.template.hideForm();
  }
});

/** Initializes the template editor form and buttons with event handlers. */
layermanager.template.initializeEditor = function() {
  jQuery('#template_form_create').click(layermanager.template.create);
  jQuery('#template_form_apply').click(layermanager.template.update);
  jQuery('#template_form_cancel').click(layermanager.template.hideForm);

  jQuery('#template_edit_button').click(function() {
    layermanager.template.showForm('edit');
  });
  jQuery('#template_delete_button').click(layermanager.template.destroy);
  jQuery('#template_create_button').click(function() {
    layermanager.template.showForm('create');
  });

  jQuery('#template_select').change(function() {
    if (jQuery('#template_form_apply').is(':visible')) {
      layermanager.template.showForm('edit');
    }
  });
};

/*******************************************************************************
*                                    Fields                                    *
*******************************************************************************/

layermanager.field = {};

/**
  * Refills the fields dropdown with field id/name pairs of the selected schema
  * from the schemaList global vairable.
  */
layermanager.field.refreshList = function() {
  var select = jQuery('#field_select');
  var schemaId = jQuery('#schema_select').val();
  var fieldList = layermanager.resources.schemas[schemaId].fields;

  select.html('');

  jQuery.each(fieldList, function(id, field) {
    var label = field.name + ' (' + field.type + ')';
    select.append(jQuery('<option>').text(label).attr({
      value: id, title: field.tip
    }));
  });

  if (jQuery('option', select).length == 0) {
    select.append('<option>No fields defined</option>').attr('disabled', true);
    jQuery('#field_edit_button,#field_delete_button').attr('disabled', true);
  } else {
    select.attr('disabled', false);
    jQuery('#field_edit_button,#field_delete_button').attr('disabled', false);
  }
};

/**
  * Shows the empty field form.
  */
layermanager.field.showForm = function() {
  jQuery('#field_form_create').show();
  jQuery('#field_form_apply').hide();
  jQuery('#field_name,#field_tip').val('');
  jQuery('#field_type').val('string').attr('disabled', false);
  jQuery('#field_form').show();
};

/** Hides the field form. */
layermanager.field.hideForm = function() {
  jQuery('#field_form').hide();
};

/**
  * Validates that a given field has valid name and type properties.
  * @param {Object} field The field object to check.
  * @return {boolean} Whether the field is valid.
  */
layermanager.field.validate = function(field) {
  var nameIsValid = Boolean(field.name.match(/^[a-zA-Z\d]+$/));
  var typeIsValid = Boolean(field.type);
  if (!nameIsValid) {
    layermanager.ui.reportError('Field name must be a non-empty alphanumeric ' +
                             'string!');
  } else if (!typeIsValid) {
    layermanager.ui.reportError('Please select a field type!');
  }
  return nameIsValid && typeIsValid;
};

/** Sends a POST request to create a new field with values from the form. */
layermanager.field.create = layermanager.util.makeHandler({
  action: 'create',
  type: 'field',
  collect: function() {
    return {
      schema_id: jQuery('#schema_select').val(),
      name: jQuery('#field_name').val(),
      type: jQuery('#field_type').val(),
      tip: jQuery('#field_tip').val()
    };
  },
  validate: layermanager.field.validate,
  succeed: function(result, fields) {
    layermanager.resources.schemas[fields.schema_id].fields[result] = {
      name: fields.name,
      type: fields.type,
      tip: fields.tip
    };
    layermanager.field.refreshList();
    jQuery('#field_select').val(result);
    layermanager.field.hideForm();
  }
});

/** Sends a POST request to delete the selected field. */
layermanager.field.destroy = layermanager.util.makeHandler({
  action: 'delete',
  type: 'field',
  collect: function() {
    return {
      schema_id: jQuery('#schema_select').val(),
      field_id: jQuery('#field_select').val()
    };
  },
  succeed: function(_, fields) {
    var fieldList = layermanager.resources.schemas[fields.schema_id].fields;
    delete fieldList[fields.field_id];
    layermanager.field.refreshList();
    layermanager.field.hideForm();
  }
});

/** Initializes the field editor form and buttons with event handlers. */
layermanager.field.initializeEditor = function() {
  jQuery('#field_form_create').click(layermanager.field.create);
  jQuery('#field_delete_button').click(layermanager.field.destroy);
  jQuery('#field_form_cancel').click(layermanager.field.hideForm);
  jQuery('#field_create_button').click(layermanager.field.showForm);
};

/*******************************************************************************
*                                     Main                                     *
*******************************************************************************/

/** Initializes the main schemas dropdown, the togglers and the forms. */
layermanager.schema.initialize = function() {
  layermanager.ui.setupTogglers();
  layermanager.schema.refreshList();
  layermanager.schema.initializeEditor();
  layermanager.template.initializeEditor();
  layermanager.field.initializeEditor();
};

google.setOnLoadCallback(layermanager.schema.initialize);
