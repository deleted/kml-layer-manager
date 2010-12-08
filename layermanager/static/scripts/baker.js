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
 * @fileoverview Script for the baking/auto-regionation page.
 */

layermanager.baker = {};

/** Sets up handler for the Bake button. */
layermanager.baker.initialize = function() {
  jQuery('#bake').click(function() {
    jQuery(this).attr('disabled', true);
    jQuery.ajax({
      type: 'POST',
      url: '/baker-create/' + layermanager.resources.layer.id,
      complete: function(xhr) {
        if (xhr.status >= 200 && xhr.status < 300) {
          jQuery('#bake_message').text('Layer baking started successfully.');
        } else {
          jQuery('#bake').attr('disabled', false);
          jQuery('#bake_message').html('Layer baking could not be started.' +
                                       '<br />' + xhr.responseText);
        }
      }
    });
  });
};

google.setOnLoadCallback(layermanager.baker.initialize);
