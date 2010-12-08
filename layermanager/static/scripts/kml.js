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
 * @fileoverview Script for the KML preview page.
 */

layermanager.kml = {};

/**
 * Dynamically loads the KML representation of the layer.
 */
layermanager.kml.loadKml = function() {
  jQuery.ajax({
    url: '/serve/' + layermanager.resources.layer.id + '/root.kml?pretty',
    dataType: 'text',
    complete: function(xhr) {
      if (xhr.responseText) {
        var response = xhr.responseText;
      } else {
        var response = 'An error occurred while generating KML.';
      }
      jQuery('#kml_text').val(response).removeClass('kml-loading');
    }
  });
};

google.setOnLoadCallback(layermanager.kml.loadKml);
