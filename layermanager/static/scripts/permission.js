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
 * @fileoverview Event handlers for the permission editing page.
 */

layermanager.permission = {};

/**
  * Prompts the user for an email address, and if one is entered, creates a new
  * permissions row for a user with that email.
  */
layermanager.permission.addUser = function() {
  var newUser = prompt('Please enter an email address of the user:');
  if (newUser !== null) {
    if (jQuery('input[name=users][value="' + newUser + '"]').length) {
      layermanager.ui.reportError('User already exists.');
    } else if (newUser.match(/^[^<>@]+@[^<>@]+\.[^<>@]+$/)) {
      var userInput = jQuery('<input type="hidden" name="users">');
      userInput.val(newUser);
      var firstCell = jQuery('<td>').append(userInput).append(newUser);
      var row = jQuery('<tr>').append(firstCell);

      for (var i = 0; i < layermanager.resources.permission_types.length; i++) {
        var checkbox = jQuery('<input type="checkbox">');
        var type = layermanager.resources.permission_types[i];
        checkbox.attr({
          name: newUser + '_' + type,
          'class': 'permission-' + type
        });
        row.append(jQuery('<td>').append(checkbox));
      }

      row.insertBefore('#permissions_table tr:last-child');
    } else {
      layermanager.ui.reportError('Invalid email address given.');
    }
  }
};

/**
  * Checks all adjacent checkboxes if the one that triggered the event is
  * checked.
  * @this {Element}
  */
layermanager.permission.checkAllPermissions = function() {
  if (jQuery(this).is(':checked')) {
    jQuery('input', jQuery(this).closest('tr')).attr('checked', true);
  }
};

/**
  * Unchecks all adjacent checkboxes if the one that triggered the event is
  * unchecked.
  * @this {Element}
  */
layermanager.permission.clearAllPermissions = function() {
  if (!jQuery(this).is(':checked')) {
    jQuery('input', jQuery(this).closest('tr')).attr('checked', false);
  }
};

/**
  * Checks the access permission checkbox on the same row as the one that
  * triggered the event if the latter is checked.
  * @this {Element}
  */
layermanager.permission.checkAccessPermission = function() {
  if (jQuery(this).is(':checked')) {
    var checkbox = jQuery('.permission-access', jQuery(this).closest('tr'));
    checkbox.attr('checked', true);
  }
};

/**
  * Clears the manage permission checkbox on the same row as the one that
  * triggered the event if the latter is unchecked.
  * @this {Element}
  */
layermanager.permission.clearManagePermission = function() {
  if (!jQuery(this).is(':checked')) {
    var checkbox = jQuery('.permission-manage', jQuery(this).closest('tr'));
    checkbox.attr('checked', false);
  }
};

/**
  * Collects all the permissions in the form and submits them. On success,
  * removes any user permission rows with no permissions.
  */
layermanager.permission.submitPermissions = layermanager.util.makeHandler({
  action: 'update',
  type: 'permission',
  collect: function() {
    return jQuery('#permissions_form').serializeArray();
  },
  validate: function() {
    if (jQuery('.permission-manage:checked').length == 0) {
      layermanager.ui.reportError('A layer must have at least one manager.');
    } else {
      return true;
    }
  },
  succeed: function() {
    jQuery('tr').each(function() {
      var inputs = jQuery('input[type=checkbox]', this);
      if (inputs.length && !inputs.is(':checked')) jQuery(this).detach();
    });
  }
});

/**
  * Initializes the event handlers for the checkboxes and buttons on the page.
  */
layermanager.permission.initialize = function() {
  jQuery('#permissions_new').click(layermanager.permission.addUser);
  jQuery('#permission_submit').click(layermanager.permission.submitPermissions);

  jQuery('.permission-access').live(
      'click', layermanager.permission.clearAllPermissions);
  jQuery('.permission-manage').live(
      'click', layermanager.permission.checkAllPermissions);
  jQuery(':checkbox:not(.permission-access)').live(
      'click', layermanager.permission.checkAccessPermission);
  jQuery(':checkbox:not(.permission-manage)').live(
      'click', layermanager.permission.clearManagePermission);
};

google.setOnLoadCallback(layermanager.permission.initialize);
