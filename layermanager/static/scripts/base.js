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
 * @fileoverview A collection of basic utility functions that are used
 * throughout the application.
 */

google.load('jquery', '1.4.2');

/** The UI functions namespace. */
layermanager.ui = {};
/** The formatting functions namespace. */
layermanager.format = {};
/** The general utility functions namespace. */
layermanager.util = {};

/**
  * The icon to use for the icons selector drop-down.
  * @type {string}
  * @const
  */
layermanager.ui.DROPDOWN_ICON = '/static/img/dropdown_arrow.png';
/**
  * The icon used to signify no image being selected.
  * @type {string}
  * @const
  */
layermanager.ui.NO_IMAGE_ICON = '/static/img/no_image.png';


/**
  * A generic error function that displays an error message in a modal popup.
  * @param {string} error The error message to show. May contain HTML code.
  */
layermanager.ui.reportError = function(error) {
  if (!error) {
    error = 'An unexpected error has occurred. Please wait a moment and ' +
            'retry your operation again.';
  }
  layermanager.ui.showModalBox('<div id="error">' + error + '</div>');
};

/**
  * Sets up the Zippy-like togglers on the current page. Every pair of
  * consecutive elements where the first has a "toggler" class and the second a
  * "togglee" class will act as a Zippy. If the toggler has an .untoggleable
  * class, toggling is disabled.
  */
layermanager.ui.setupTogglers = function() {
  jQuery('.toggler').click(function() {
    if (!jQuery(this).is('.untoggleable')) {
      var togglee = jQuery(this).next('.togglee');
      if (togglee.length) {
        jQuery(this).toggleClass('toggled');
        togglee.toggle();
      }
    }
  });
};

/**
  * Converts a <select> element into a visual selector for icons, limited to
  * 16x16 pixels in size.
  * @param {Object} selects The jQuery-wrapped <select> element(s) to convert.
  *    The value of this element will be updated when icon selection changes.
  */
layermanager.ui.visualizeIconSelect = function(selects) {
  jQuery(selects).each(function() {
    var $select = jQuery(this);
    var selected = jQuery('<div class="icon-selected"><div>None</div></div>');
    var dropdown = jQuery('<div class="icon-dropdown">');

    jQuery('option', $select).each(function() {
      var id = jQuery(this).val();
      var name = jQuery(this).text().replace(/^\s+|\s+$/g, '');
      var url = layermanager.util.getResourceUrl(id, 16);
      var backgroundImage = 'url("' + url + '")';

      var block = jQuery('<div>').text(name).click(function() {
        selected.css('background-image', backgroundImage);
        jQuery('div', selected).text(jQuery(this).text());
        $select.val(id);
        dropdown.slideUp('fast');
      }).css('background-image', backgroundImage);
      block.attr('rel', id).appendTo(dropdown);
    });

    selected.click(function() {
      if (!jQuery(this).is('.disabled')) {
        var position = jQuery(this).position();
        dropdown.css({
          top: position.top + jQuery(this).height() + 4,
          left: position.left
        }).slideToggle('fast');
      }
    }).append('<img src="' + layermanager.ui.DROPDOWN_ICON + '">');

    $select.change(function() {
      var selector = 'div[rel="' + jQuery(this).val() + '"]';
      var selectedOption = jQuery(selector, dropdown);
      selected.css('background-image', selectedOption.css('background-image'));
      jQuery('div', selected).text(selectedOption.text());
    }).change();

    dropdown.hide();
    $select.hide().after(selected).after(dropdown);
  });
};

/**
  * Converts a <select> element into a visual selector for images.
  * @param {Object} selects The jQuery-wrapped <select> element(s) to convert.
  *    The value of this element will be updated when image selection changes.
  */
layermanager.ui.visualizeImageSelect = function(selects) {
  jQuery(selects).each(function() {
    var $select = jQuery(this);
    var container = jQuery('<div class="image-list">');

    jQuery('option', $select).each(function() {
      var id = jQuery(this).val();
      var name = jQuery(this).text().replace(/^\s+|\s+$/g, '');
      if (id) {
        var url = layermanager.util.getResourceUrl(id);
      } else {
        var url = layermanager.ui.NO_IMAGE_ICON;
      }

      var block = jQuery('<img class="image-block">').hover(function() {
        block.toggleClass('hover');
      }).click(function() {
        if (block.is('.selected')) return;
        block.siblings('.image-block').removeClass('selected');
        block.addClass('selected');
        $select.val(block.data('id'));
      }).attr({src: url, title: name}).data('id', id).appendTo(container);

      if (jQuery(this).is(':selected')) {
        block.addClass('selected');
      }
    });

    $select.hide().after(container);
  });
};

/**
  * Shows a modal popup box with the specified HTML contents, an Ok button and
  * optionally a Cancel button.
  * @param {(string|Object)} contents The contents of the popup box. May be a
  *     string or a jQuery-wrapped element or set of elements (anything that
  *     jQuery can append()).
  * @param {function()=} opt_okCallback A function to call when clicking the Ok
  *     button. By default, simply closes the popup.
  * @param {function()=} opt_cancelCallback A function to call when clicking the
  *     cancel button. If not specified, the cancel button is not displayed.
  */
layermanager.ui.showModalBox = function(contents, opt_okCallback,
                                     opt_cancelCallback) {
  if (jQuery('#modal_box').length) layermanager.ui.hideModalBox();

  var shader = jQuery('<div id="background_shader">');
  shader.height(jQuery(window).height()).width(jQuery(window).width());
  shader.appendTo('body');
  if (opt_cancelCallback === undefined && opt_okCallback === undefined) {
    shader.click(layermanager.ui.hideModalBox);
  }

  contents = jQuery('<div id="modal_box_contents">').append(contents);

  var box = jQuery('<div id="modal_box">');
  var padder = jQuery('<div>');
  var container = jQuery('<div>').append(contents);
  var buttonsContainer = jQuery('<div id="modal_box_buttons">');

  var okButton = jQuery('<input id="modal_box_ok" type="button" value=" Ok ">');
  okButton.click(opt_okCallback || layermanager.ui.hideModalBox);
  okButton.appendTo(buttonsContainer);

  if (opt_cancelCallback) {
    var cancelButton = jQuery('<input id="modal_box_cancel" type="button" ' +
                              'value="Cancel">');
    cancelButton.click(opt_cancelCallback);
    cancelButton.appendTo(buttonsContainer);
  }

  buttonsContainer.appendTo(container);
  container.appendTo(padder);
  padder.appendTo(box);
  box.appendTo('body');

  box.css({
    top: (jQuery(window).height() - box.height()) / 2,
    left: (jQuery(window).width() - box.width()) / 2
  });
};

/**
 * Hides the modal popup box and its shader if either is visible.
 */
layermanager.ui.hideModalBox = function() {
  jQuery('#background_shader,#modal_box').remove();
};

/**
  * Forces an <input> (or multiple <input>s) to limit entry to positive integer
  * values.
  * @param {Object} inputs The jQuery-wrapped <input>s to convert.
  */
layermanager.ui.initIntegerField = function(inputs) {
  inputs.keyup(function() {
    var value = jQuery(this).val();
    if (/^[0-9]*$/.test(value)) return true;
    value = value.replace(/[^0-9]/g, '');
    jQuery(this).val(value);
  }).keypress(function(event) {
    var character = String.fromCharCode(event.charCode);
    return event.keyCode == 8 || event.ctrlKey || /\d/.test(character);
  }).blur(function() { jQuery(this).keyup(); });
};

/**
  * Forces an <input> (or multiple <input>s) to limit entry to float values.
  * @param {Object} inputs The jQuery-wrapped <input>s to convert.
  * @param {boolean=} opt_allowNegative Whether to allow negative values.
  *     Defaults to false.
  */
layermanager.ui.initFloatField = function(inputs, opt_allowNegative) {
  inputs.keyup(function() {
    var value = jQuery(this).val();
    var sign = '';
    if (opt_allowNegative && value[0] == '-') {
      value = value.slice(1);
      sign = '-';
    }

    if (/^[0-9]*\.?[0-9]*$/.test(value)) return true;
    value = value.replace(/[^0-9.]/g, '');

    var dotSeparated = /\./.exec(value);
    if (dotSeparated != null) {
      var postDot = value.substring(dotSeparated.index +
                                    dotSeparated[0].length);
      postDot = postDot.replace(/\./g, '');
      value = value.substring(0, dotSeparated.index) + '.' + postDot;
    }

    jQuery(this).val(sign + value);
  }).keypress(function(event) {
    var value = jQuery(this).val();
    var character = String.fromCharCode(event.charCode);
    // On IE this will allow extra minus signs due to lack of selectionStart.
    // That is taken care of by the keyup() handler.
    return Boolean(event.keyCode == 8 ||
                   event.ctrlKey ||
                   /\d/.test(character) ||
                   (character == '.' && value.indexOf('.') == -1) ||
                   (opt_allowNegative && character == '-' &&
                    value.indexOf('-') == -1 && !this.selectionStart));
  }).blur(function() { jQuery(this).keyup(); });
};

/**
  * Converts an <input> (or <input>s) into a color picker control.
  * NOTE: Uses the ColorPicker jQuery plugin.
  * @param {Object} inputs The jQuery-wrapped <input>s to convert to color
  *    pickers.
  * @param {?boolean} opt_includeAlpha Whether to allow the user to select an
  *    alpha color. Defaults to true.
  */
layermanager.ui.initColorPicker = function(inputs, opt_includeAlpha) {
  if (!jQuery.fn.ColorPicker) return;
  if (opt_includeAlpha === undefined) opt_includeAlpha = true;
  jQuery(inputs).each(function() {
    var input = jQuery(this);
    var color = input.val() || 'ffffffff';
    input.ColorPicker({
      color: color,
      alpha: opt_includeAlpha,
      palette: false,
      onShow: function(colorPicker) {
        jQuery(colorPicker).fadeIn(500);
        return false;
      },
      onHide: function(colorPicker) {
        jQuery(colorPicker).fadeOut(500);
        return false;
      },
      onChange: function(hsb, hex, rgb) {
        var hexMinusAlpha = hex.slice(2);
        if (opt_includeAlpha) {
          input.val(hex);
        } else {
          input.val(hexMinusAlpha);
        }
        input.css({
          'color': '#' + hexMinusAlpha,
          'background-color': '#' + hexMinusAlpha
        });
      }
    }).addClass('color-picker').attr('spellcheck', 'false').focus(function() {
      input.blur();
    }).css({
      'color': '#' + color.slice(2),
      'background-color': '#' + color.slice(2)
    });
  });
};

/**
  * Converts an <input> (or <input>s) into a date picker control.
  * NOTE: Uses the DatePicker jQuery plugin.
  * @param {Object} inputs The jQuery-wrapped <input>s to convert.
  */
layermanager.ui.initDateField = function(inputs) {
  if (!jQuery.fn.datepicker) return;
  inputs.each(function() {
    var that = this;
    jQuery(this).datepicker({
      shownOn: 'both',
      dateFormat: 'YMD-'
    }).keypress(function() {
      return false;
    });
  });
};

/**
  * Converts a color from an ABGR to an ARGB representation.
  * @param {string} abgr The color in ABGR.
  * @return {string} The color in ARGB.
  */
layermanager.format.ABGRToARGBColor = function(abgr) {
  return abgr.slice(0, 2) + abgr.slice(6, 8) + abgr.slice(4, 6) +
         abgr.slice(2, 4);
};

/**
  * Converts a color from an ARGB to an ABGR representation.
  * @param {string} argb The color in ARGB.
  * @return {string} The color in ABGR.
  */
layermanager.format.ARGBToABGRColor = layermanager.format.ABGRToARGBColor;

/**
  * Formats a coordinate as a sexagesimal string.
  * @param {number} coordinate The numeric value of the coordinate to format.
  * @param {string} suffix A suffix to append, e.g. "North".
  * @return {string} The formatted number.
  */
layermanager.format.formatCoordinate = function(coordinate, suffix) {
  var whole = parseInt(coordinate, 10);
  var minutes = parseInt((coordinate % 1) * 60, 10);
  if (minutes.toString().length == 1) minutes = '0' + minutes;
  var seconds = parseInt((((coordinate % 1) * 60) % 1) * 60, 10);
  if (seconds.toString().length == 1) seconds = '0' + seconds;
  return whole + '&deg;' + minutes + "'" + seconds + '" ' + suffix;
};

/**
  * Formats a latitude as a sexagesimal string with a N/S suffix.
  * @param {number} latitude The latitude to format.
  * @return {string} The formatted latitude.
  */
layermanager.format.formatLatitude = function(latitude) {
  return layermanager.format.formatCoordinate(Math.abs(latitude),
                                              (latitude >= 0) ? 'N' : 'S');
};

/**
  * Formats a longitude as a sexagesimal string with a E/W suffix.
  * @param {number} longitude The longitude to format.
  * @return {string} The formatted longitude.
  */
layermanager.format.formatLongitude = function(longitude) {
  return layermanager.format.formatCoordinate(Math.abs(longitude),
                                           (longitude >= 0) ? 'E' : 'W');
};

/**
  * Formats an altitude as a string, in meters if it's below 1000 meters, and in
  * kilometers with two decimal places otherwise.
  * @param {number} altitude The altitude to format.
  * @return {string} The formatted altitude.
  */
layermanager.format.formatAltitude = function(altitude) {
  if (Math.abs(altitude) > 1000) {
    return (Math.round(altitude / 10) / 100) + ' km';
  } else {
    return Math.round(altitude) + ' m';
  }
};


/**
  * Gets the URL for a given resource.
  * @param {(string|number)} id The If of the resource.
  * @param {number=} opt_size The maximum width or height of the thumbnail to
  *     generate. Only valid for image or icon resources.
  * @return {?string} The assembled resource URL.
  */
layermanager.util.getResourceUrl = function(id, opt_size) {
  var host = 'http://' + window.location.host;
  if (id && opt_size) {
    return host + '/serve/0/r' + id + '?resize=' + opt_size;
  } else if (id) {
    return host + '/serve/0/r' + id;
  } else {
    return null;
  }
};

/**
  * Creates a function to send a create/update/delete request to the server. The
  * resulting function expects to be called as an event handler with "this" set
  * to the element which initiated the request. This element is disabled while
  * the request is in progress.
  * @param {Object} options An object describing the handler. Includes:
  *     * action: The type of request to send: "create", "update", "delete" or
  *         "move". Used to construct the URL.
  *     * type: The type of object to operate on, such as "folder" or "schema".
  *         Used to construct the URL.
  *     * collect: A function called to collect the fields to send to the
  *         server. It is called in the context of the object which triggered
  *         the event and with the arguments went to the handler. If not
  *         specified, no post argumetns are sent.
  *     * validate: A function to call with the collected fields before sending
  *         the request to the server. If this function does not return true,
  *         the request is aborted. If not specified, the check is skipped.
  *     * succeed: A function to call if the request succeeds. The server's
  *         response and the fields that were sent are passed as arguments.
  *     * fail: A function to call if the request fails. The server's response
  *         is passed as arguments. Defaults to layermanager.ui.reportError().
  * @return {function()} The resulting handler fucntion.
  */
layermanager.util.makeHandler = function(options) {
  options = jQuery.extend({
    collect: function() { return {}; },
    validate: function() { return true; },
    succeed: jQuery.noop,
    fail: layermanager.ui.reportError
  }, options);

  return function() {
    var that = this;
    var fields = options.collect.apply(this, arguments);
    if (options.validate(fields) === true) {
      jQuery(this).attr('disabled', true);
      // TODO: Disable the other buttons that operate on the same object.
      var url = '/' + options.type + '-' + options.action + '/' +
                layermanager.resources.layer.id;
      jQuery.ajax({
        type: 'POST',
        url: url,
        data: fields,
        complete: function(xhr) {
          jQuery(that).attr('disabled', false);
          if (xhr.status >= 200 && xhr.status < 300) {
            options.succeed(xhr.responseText, fields);
          } else {
            options.fail(xhr.responseText);
          }
        }
      });
    }
  };
};

/**
  * Check whether the supplied fields object has a non-empty name property, and
  * report an error if it doesn't.
  * @param {Object} fields The fields map.
  * @return {boolean} Whether the input object has a non-empty name property.
  */
layermanager.util.validateFieldsContainName = function(fields) {
  if (!fields.name) layermanager.ui.reportError('Name cannot be empty!');
  return Boolean(fields.name);
};
