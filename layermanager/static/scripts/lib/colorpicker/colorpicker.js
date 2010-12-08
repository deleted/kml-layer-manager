/**
 * @license
 * Color picker
 * Author: Stefan Petre www.eyecon.ro
 * Dual licensed under the MIT and GPL licenses
 *
 * Modifications: Stefan Kuhne (skuhne@google.com):
 *   - Added alpha channel
 *   - Added Revert
 *   - Added default behavior
 *   - Added default button handling
 *     Can be overwritten by changing the default option 'buttonStyle'. The user
 *     needs then to define the following css styles:
 *        The basic div which contains everything:       <name>
 *        The div which contains the overlaying artwork: <name>Image
 *        The div which contains the fill color:         <name>Color
 *        The div which contains the alpha pattern (if): <name>Alpha
 *   - Partially Google style guide conform
 *   - Added palette
 *     Can be overwritten by changing the default option 'paletteColors'
 *   - Works now in IFrames
 *   - respect the disable attribute.
 *   - ..
 */

(function($) {
    var ColorPicker = function() {
      var ids = {},
          inAction,
          charMin = 65,
          visible,
          numberPaletteEntries = 15,
//      isLessThanIE7 = parseFloat(navigator.appVersion.split('MSIE')[1]) < 7 &&
//                                 document.body.filters,
      palette = '<div class="colorpicker_palette">' +
                '<div class="colorpicker_paletteAlpha"></div>' +
                '<div class="colorpicker_paletteColor"></div></div>',
      tpl = '<div class="colorpicker"><div class="colorpicker_color"><div>' +
            '<div></div></div></div>' +
            '<div class="colorpicker_hue"><div></div></div>' +
            '<div><span class="colorpicker_new_color"></span></div>' +
            '<div><span class="colorpicker_current_color"></span></div>' +
            '<div class="colorpicker_hex"><input type="text" maxlength="6" ' +
            'size="6" /></div>' +
            '<div class="colorpicker_rgb_r colorpicker_field"><input type=' +
            '"text" maxlength="3" size="3" /><span></span></div>' +
            '<div class="colorpicker_rgb_g colorpicker_field"><input type=' +
            '"text" maxlength="3" size="3" /><span></span></div>' +
            '<div class="colorpicker_rgb_b colorpicker_field"><input type=' +
            '"text" maxlength="3" size="3" /><span></span></div>' +
            '<div class="colorpicker_rgba_a colorpicker_field" style="' +
            'display:none;"><input type="text" maxlength="3" size="3" style=' +
            '"display:none;"/><span></span></div>' +
            '<div class="colorpicker_hsb_h colorpicker_field"><input type=' +
            '"text" maxlength="3" size="3" /><span></span></div>' +
            '<div class="colorpicker_hsb_s colorpicker_field"><input type="' +
            'text" maxlength="3" size="3" /><span></span></div>' +
            '<div class="colorpicker_hsb_b colorpicker_field"><input type=' +
            '"text" maxlength="3" size="3" /><span></span></div>' +
            '<div class="colorpicker_revert"></div>' +
            '<div class="colorpicker_submit"></div>',
      tpla = '<div class="colorpicker"><div class="colorpicker_color"><div>' +
             '<div></div></div></div>' +
             '<div class="colorpicker_hue"><div></div></div>' +
             '<div><span class="colorpicker_new_Alpha"></span>' +
             '<span class="colorpicker_new_colorA"></span></div>' +
             '<div><span class="colorpicker_current_Alpha"></span>' +
             '<span class="colorpicker_current_colorA"></span></div>' +
             '<div class="colorpicker_hexrgba"><input type="text" maxlength=' +
             '"8" size="8" /></div>' +
             '<div class="colorpicker_rgba_r colorpicker_field"><input type=' +
             '"text" maxlength="3" size="3" /><span></span></div>' +
             '<div class="colorpicker_rgba_g colorpicker_field"><input type=' +
             '"text" maxlength="3" size="3" /><span></span></div>' +
             '<div class="colorpicker_rgba_b colorpicker_field"><input type=' +
             '"text" maxlength="3" size="3" /><span></span></div>' +
             '<div class="colorpicker_rgba_a colorpicker_field"><input type=' +
             '"text" maxlength="3" size="3" /><span></span></div>' +
             '<div class="colorpicker_hsb_h colorpicker_field"><input type=' +
             '"text" maxlength="3" size="3" /><span></span></div>' +
             '<div class="colorpicker_hsb_s colorpicker_field"><input type=' +
             '"text" maxlength="3" size="3" /><span></span></div>' +
             '<div class="colorpicker_hsb_b colorpicker_field"><input type=' +
             '"text" maxlength="3" size="3" /><span></span></div>' +
             '<div class="colorpicker_revert"></div>' +
             '<div class="colorpicker_submit"></div>',
      defaults = {
        eventName: 'click',
        onShow: function(colpkr) {
          $(colpkr).fadeIn(200);
          return true;
        },
        onBeforeShow: function(){},
        onHide: function(colpkr) {
          $(colpkr).fadeOut(100);
          return true;
        },
        onChange: function() {},
        onSubmit: function() {},
        alpha: false,
        color: 'ffff0000',
        livePreview: true,
        flat: false,
        palette: true,
        paletteColors: [],
        buttonStyle: 'colorPicker_button',
        document: document,
        window: window
      },
      fillRGBFields = function(hsb, cal) {
        var rgb = HSBToRGB(hsb);
        var self = $(cal).data('colorpicker');
        self.fields
            .eq(1).val(Math.round(rgb.r)).end()
            .eq(2).val(Math.round(rgb.g)).end()
            .eq(3).val(Math.round(rgb.b)).end()
            .eq(4).val(Math.round(rgb.a)).end();
      },
      fillHSBFields = function(hsb, cal) {
        var self = $(cal).data('colorpicker');
        self.fields
            .eq(5).val(Math.round(hsb.h)).end()
            .eq(6).val(Math.round(hsb.s)).end()
            .eq(7).val(Math.round(hsb.b)).end()
          .eq(4).val(Math.round(hsb.a)).end();
      },
      fillHexFields = function(hsb, cal) {
        var self = $(cal).data('colorpicker');
          self.fields.eq(0).val(HSBToHex(hsb, !self.alpha)).end();
      },
      setSelector = function(hsb, cal) {
        // Setting the color in the color picker selector.
        var self = $(cal).data('colorpicker');
        var color = '#' + HSBToHex({h: hsb.h, s: 100, b: 100, a: 255}, true);
        self.selector.css({backgroundColor: color});
        self.selectorIndic.css({
          left: parseInt(150 * hsb.s / 100, 10),
          top: parseInt(150 * (100 - hsb.b) / 100, 10)
        });
      },
      setHue = function(hsb, cal) {
        var self = $(cal).data('colorpicker');
        self.hue.css('top', parseInt(150 - 150 * hsb.h / 360, 10));
      },
      setCurrentColor = function(hsb, cal) {
        var self = $(cal).data('colorpicker');
        var color = '#' + HSBToHex(hsb, true);
        self.currentColor.css({backgroundColor: color});
        if (self.alpha) {
          setAlpha(hsb.a, self.currentColor);
        }
      },
      setNewColor = function(hsb, cal) {
        var self = $(cal).data('colorpicker');
        var color = '#' + HSBToHex(hsb, true);
        self.newColor.css({backgroundColor: color});
        if (self.alpha) {
          setAlpha(hsb.a, self.newColor);
        }
      },
      setAlpha = function(alpha, obj) {
        obj.css({ visibility: alpha > 0 ? 'visible' : 'hidden' });
        if (alpha > 0 && alpha <= 255) {
// I think we do not need this - however I leave it in for the case that we need
// it in the end anyways.
//          if (isLessThanIE7) {
//            var src = obj.attr('pngSrc');
//            if (src != null && (src.indexOf('colorpicker_button.gif') != -1))
//              obj.css({
//                filter: 'progid:DXImageTransform.Microsoft.' +
//                        'AlphaImageLoader(src=\'' + src + '\',
//                         sizingMethod=\'scale\') progid:DXImageTransform.' +
//                         'Microsoft.Alpha(opacity=' + (1.0 - alpha) + ')' });
//            else obj.css({ opacity: 1.0 - alpha / 255 });
//          } else
          obj.css({ opacity: alpha / 255 });
        } else {
// I think we do not need this - however I leave it in for the case that we need
// it in the end anyways.
//          if (isLessThanIE7) {
//            var src = obj.attr('pngSrc');
//            if (src != null && (src.indexOf('colorpicker_button.gif') != -1))
//              obj.css({
//                filter: 'progid:DXImageTransform.Microsoft.AlphaImageLoader' +
//                        '(src=\'' + src + '\', sizingMethod=\'scale\')' });
//            else obj.css({ opacity: '' });
//          } else
          obj.css({ opacity: '' });
        }
      },
      keyDown = function(ev) {
        var pressedKey = ev.charCode || ev.keyCode || -1;
        if ((pressedKey > charMin && pressedKey <= 90) || pressedKey == 32) {
          return false;
        }
        var cal = $(this).parent().parent();
        var self = cal.data('colorpicker');
        if (self.livePreview === true) {
          change.apply(this);
        }
      },
      change = function(ev) {
        var cal = $(this).parent().parent(), col;
        var self = cal.data('colorpicker');
        if (this.parentNode.className.indexOf(
              self.alpha ? '_hexrgba' : '_hex') > 0) {
          self.color = col = HexToHSB(fixHex(this.value));
        } else if (this.parentNode.className.indexOf('_hsb') > 0) {
          self.color = col = fixHSB({
            h: parseInt(self.fields.eq(5).val(), 10),
            s: parseInt(self.fields.eq(6).val(), 10),
            b: parseInt(self.fields.eq(7).val(), 10),
            a: parseInt(self.fields.eq(4).val(), 10)
          });
        } else {
          self.color = col = RGBToHSB(fixRGB({
            r: parseInt(self.fields.eq(1).val(), 10),
            g: parseInt(self.fields.eq(2).val(), 10),
            b: parseInt(self.fields.eq(3).val(), 10),
            a: parseInt(self.fields.eq(4).val(), 10)
          }));
        }
        if (ev) {
          fillRGBFields(col, cal.get(0));
          fillHexFields(col, cal.get(0));
          fillHSBFields(col, cal.get(0));
        }
        setSelector(col, cal.get(0));
        setHue(col, cal.get(0));
        setNewColor(col, cal.get(0));

        // Set the thumbnail accordingly.
        var color = HSBToHex(col, true);
        self.button.css('backgroundColor', '#' + color);
        if (self.alpha) {
          self.buttonAlpha.css('opacity', 1.0 - col.a / 255);
        }
        // And call the object accordingly.
        self.onChange.apply(cal, [col, HSBToHex(col, false), HSBToRGB(col)]);
      },
      blur = function(ev) {
        var cal = $(this).parent().parent();
        var self = cal.data('colorpicker');
        self.fields.parent().removeClass('colorpicker_focus');
      },
      focus = function() {
        var self = $(this).parent().parent().data('colorpicker');
        charMin = this.parentNode.className.indexOf(
                    self.alpha ? '_hexrgba' : '_hex') > 0 ? 70 : 65;
        self.fields.parent().removeClass('colorpicker_focus');
        $(this).parent().addClass('colorpicker_focus');
      },
      downIncrement = function(ev) {
        var self = $(this).parent().parent().data('colorpicker');
        var field = $(this).parent().find('input').focus();
        var current = {
          el: $(this).parent().addClass('colorpicker_slider'),
          max: this.parentNode.className.indexOf('_hsb_h') > 0 ? 360 :
                 (this.parentNode.className.indexOf('_hsb') > 0 ? 100 : 255),
          y: ev.pageY,
          field: field,
          val: parseInt(field.val(), 10),
          preview: self.livePreview
        };
        $(document).bind('mouseup', current, upIncrement);
        $(document).bind('mousemove', current, moveIncrement);
      },
      moveIncrement = function(ev) {
        ev.data.field.val(Math.max(0, Math.min(ev.data.max,
            parseInt(ev.data.val + ev.pageY - ev.data.y, 10))));
        if (ev.data.preview) {
          change.apply(ev.data.field.get(0), [true]);
        }
        return false;
      },
      upIncrement = function(ev) {
        var self = $(this).parent().parent().data('colorpicker');
        change.apply(ev.data.field.get(0), [true]);
        ev.data.el.removeClass('colorpicker_slider')
          .find('input').focus();
        $(this).unbind('mouseup', upIncrement);
        $(this).unbind('mousemove', moveIncrement);
        return false;
      },
      downHue = function(ev) {
        var self = $(this).parent().data('colorpicker');
        var current = {
          cal: $(this).parent(),
          y: $(this).offset().top
        };
        current.preview = current.cal.data('colorpicker').livePreview;
        $(document).bind('mouseup', current, upHue);
        $(document).bind('mousemove', current, moveHue);
      },
      moveHue = function(ev) {
        var self = ev.data.cal.data('colorpicker');
        change.apply(
            self.fields
                .eq(5)
                .val(parseInt(360 * (150 - Math.max(0, Math.min(150,
                      (ev.pageY - ev.data.y)))) / 150, 10))
                .get(0),
            [ev.data.preview]);
        return false;
      },
      upHue = function(ev) {
        var self = ev.data.cal.data('colorpicker');
        fillRGBFields(self.color, ev.data.cal.get(0));
        fillHexFields(self.color, ev.data.cal.get(0));
        $(document).unbind('mouseup', upHue);
        $(document).unbind('mousemove', moveHue);
        return false;
      },
      downSelector = function(ev) {
        var self = $(this).parent().data('colorpicker');
        var current = {
          cal: $(this).parent(),
          pos: $(this).offset()
        };
        current.preview = self.livePreview;
        $(document).bind('mouseup', current, upSelector);
        $(document).bind('mousemove', current, moveSelector);
      },
      moveSelector = function(ev) {
        var self = ev.data.cal.data('colorpicker');
        change.apply(
            self.fields
                .eq(7)
                .val(parseInt(100 * (150 - Math.max(0, Math.min(150,
                      (ev.pageY - ev.data.pos.top)))) / 150, 10))
                .end()
                .eq(6)
                .val(parseInt(100 * (Math.max(0, Math.min(150,
                      (ev.pageX - ev.data.pos.left)))) / 150, 10))
                .get(0),
            [ev.data.preview]);
        return false;
      },
      upSelector = function(ev) {
        var self = ev.data.cal.data('colorpicker');
        fillRGBFields(self.color, ev.data.cal.get(0));
        fillHexFields(self.color, ev.data.cal.get(0));
        $(document).unbind('mouseup', upSelector);
        $(document).unbind('mousemove', moveSelector);
        return false;
      },
      enterSubmit = function(ev) {
        $(this).addClass('colorpicker_focus');
      },
      leaveSubmit = function(ev) {
        $(this).removeClass('colorpicker_focus');
      },
      clickSubmit = function(ev) {
        var cal = $(this).parent();
        var self = cal.data('colorpicker');
        var col = self.color;
        self.origColor = col;
        setCurrentColor(col, cal.get(0));
        self.onSubmit(col, HSBToHex(col, false), HSBToRGB(col), self.el);
      },
      enterRevert = function(ev) {
        $(this).addClass('colorpicker_focus');
      },
      leaveRevert = function(ev) {
        $(this).removeClass('colorpicker_focus');
      },
      clickRevert = function(ev) {
        var cal = $(this).parent();
        var self = cal.data('colorpicker');
        var col = self.origColor;
        self.color = col;
        fillRGBFields(col, cal.get(0));
        fillHSBFields(col, cal.get(0));
        fillHexFields(col, cal.get(0));
        setHue(col, cal.get(0));
        setSelector(col, cal.get(0));
        setNewColor(col, cal.get(0));
        setCurrentColor(col, cal.get(0));
        self.onChange(col, HSBToHex(col, false), HSBToRGB(col), self.el);
      },
      show = function(ev) {
        var panelHeight = 176;
        var panelWidth = 356;
        var cal = $(document).find('#' + $(this).data('colorpickerId'));
        var self = cal.data('colorpicker');
        if (this.disable) {
          if (self.isShown) {
            cal.hide();
          }
          self.isShown = false;
          return false;
        }
        if (self.isShown) {
          // Hide the dialog again if the user hits it twice.
          if (self.onHide.apply(this, [cal.get(0)]) != false) {
            cal.hide();
          }
          self.isShown = false;
          $(document).bind('mousedown', {cal: cal}, hide);
          if (document != self.document) {
            $(self.document).bind('mousedown', {cal: cal}, hide);
          }
          return false;
        }
        self.isShown = true;
        self.onBeforeShow.apply(this, [cal.get(0)]);
        // Get the position of the object relative to the document.
        var contentRelativePos = $(this).offset();
        // Get any scroll offsets we have to include.
        var contentScroll = {left: 0, top : 0};
        if (self.document == document) {
          // No need for modifications since the control will move with the
          // button.
        } else {
          contentScroll.left = $(self.document).scrollLeft();
          contentScroll.top = $(self.document).scrollTop();
        }
        // Get the size and pos of the window viewport
        var viewPort = getViewport(self);
        // If the position is relative to a sub frame - make it absolute to the
        // window.
        var relativeShift = {left: 0, top: 0};
        if (self.document != document) {
          // We need to find the offset of the document into the view.
          var dx = 0;
          var dy = 0;
          var iframes = $(document).find('iframe');
          for (var i = 0; i < iframes.length; i++) {
            if (iframes[i].contentDocument == self.document) {
              var offset = jQuery(iframes[i]).offset();
              relativeShift.left = offset.left;
              relativeShift.top = offset.top;
            }
          }
        }
        var top = contentRelativePos.top + this.offsetHeight -
                  contentScroll.top + relativeShift.top;
        var left = contentRelativePos.left - contentScroll.left +
                   relativeShift.left;
        // Finally we have to make sure that we stay within the bounds.
        if (top + panelHeight > viewPort.top + viewPort.height) {
          top -= this.offsetHeight + panelHeight;
        }
        if (left + panelWidth > viewPort.left + viewPort.width) {
          left -= panelWidth;
        }
        cal.css({left: Math.round(left) + 'px', top: Math.round(top) + 'px'});
        if (self.onShow.apply(this, [cal.get(0)]) != false) {
          cal.show();
        }
        $(document).bind('mousedown', {cal: cal}, hide);
        // We have to add the click handler from the main and to the sub
        // page.
        if (document != self.document) {
          $(self.document).bind('mousedown', {cal: cal}, hide);
        }

        return false;
      },
      hide = function(ev) {
        var self = ev.data.cal.data('colorpicker');
        self.isShown = false;
        var cal = ev.data.cal;
        if (!isChildOf(cal.get(0), ev.target, cal.get(0))) {
          if (cal.data('colorpicker').onHide.apply(
              this, [cal.get(0)]) != false) {
            cal.hide();
          }
          $(document).unbind('mousedown', hide);
          // We have to remove the click handler from the main and from
          // the sub page.
          if (document != self.document) {
            $(self.document).unbind('mousedown', hide);
          }
        }
      },
      isChildOf = function(parentEl, el, container) {
        if (parentEl == el) {
          return true;
        }
        if (parentEl.contains) {
          return parentEl.contains(el);
        }
        if (parentEl.compareDocumentPosition) {
          return !!(parentEl.compareDocumentPosition(el) & 16);
        }
        var prEl = el.parentNode;
        while (prEl && prEl != container) {
          if (prEl == parentEl)
            return true;
          prEl = prEl.parentNode;
        }
        return false;
      },
      getViewport = function(self) {
        var m = self.document.compatMode == 'CSS1Compat';
        return {
          left : self.document != document ? 0 : $(document).scrollLeft(),
          top : self.document != document ? 0 : $(document).scrollTop(),
          width : window.innerWidth ||
                (m ? document.documentElement.clientWidth :
                     document.body.clientWidth),
          height : window.innerHeight ||
                 (m ? document.documentElement.clientHeight :
                      document.body.clientHeight)
        };
      },
      fixHSB = function(hsb) {
        return {
          a: Math.min(255, Math.max(0, hsb.a)),
          h: Math.min(360, Math.max(0, hsb.h)),
          s: Math.min(100, Math.max(0, hsb.s)),
          b: Math.min(100, Math.max(0, hsb.b))
        };
      },
      fixRGB = function(rgb) {
        return {
          a: Math.min(255, Math.max(0, rgb.a)),
          r: Math.min(255, Math.max(0, rgb.r)),
          g: Math.min(255, Math.max(0, rgb.g)),
          b: Math.min(255, Math.max(0, rgb.b))
        };
      },
      fixHex = function(hex) {
        // Fill the color components as 00
        var len = 6 - hex.length;
        if (len > 0) {
          var o = [];
          for (var i = 0; i < len; i++) {
              o.push('0');
          }
          o.push(hex);
          hex = o.join('');
        }
        // Fill the alpha as ff
        len = 8 - hex.length;
        if (len > 0) {
          var o = [];
          for (var i = 0; i < len; i++) {
            o.push('F');
          }
          o.push(hex);
          hex = o.join('');
        }
        return hex;
      },
      HexToRGB = function(hex) {
        var hex = parseInt(((hex.indexOf('#') > -1) ? hex.substring(1) : hex),
                           16);
        return {a: (hex >> 24 & 0xff),
                r: (hex & 0xff0000) >> 16,
                g: (hex & 0x00FF00) >> 8,
                b: (hex & 0x0000FF)};
      },
      HexToHSB = function(hex) {
        return RGBToHSB(HexToRGB(hex));
      },
      RGBToHSB = function(rgb) {
        var hsb = {
          a: rgb.a,
          h: 0,
          s: 0,
          b: 0
        };
        var min = Math.min(rgb.r, rgb.g, rgb.b);
        var max = Math.max(rgb.r, rgb.g, rgb.b);
        var delta = max - min;
        hsb.b = max;
        hsb.s = max != 0 ? 255 * delta / max : 0;
        if (hsb.s != 0) {
          if (rgb.r == max) {
            hsb.h = (rgb.g - rgb.b) / delta;
          } else if (rgb.g == max) {
            hsb.h = 2 + (rgb.b - rgb.r) / delta;
          } else {
            hsb.h = 4 + (rgb.r - rgb.g) / delta;
          }
        } else {
          hsb.h = -1;
        }
        hsb.h *= 60;
        if (hsb.h < 0) {
          hsb.h += 360;
        }
        hsb.s *= 100 / 255;
        hsb.b *= 100 / 255;
        return hsb;
      },
      HSBToRGB = function(hsb) {
        var rgb = {};
        var h = Math.round(hsb.h);
        var s = Math.round(hsb.s * 255 / 100);
        var v = Math.round(hsb.b * 255 / 100);
        if (s == 0) {
          rgb.r = rgb.g = rgb.b = v;
        } else {
          var t1 = v;
          var t2 = (255 - s) * v / 255;
          var t3 = (t1 - t2) * (h % 60) / 60;
          if (h == 360) h = 0;
          if (h < 60) {rgb.r = t1; rgb.b = t2; rgb.g = t2 + t3}
          else if (h < 120) {rgb.g = t1; rgb.b = t2; rgb.r = t1 - t3}
          else if (h < 180) {rgb.g = t1; rgb.r = t2; rgb.b = t2 + t3}
          else if (h < 240) {rgb.b = t1; rgb.r = t2; rgb.g = t1 - t3}
          else if (h < 300) {rgb.b = t1; rgb.g = t2; rgb.r = t2 + t3}
          else if (h < 360) {rgb.r = t1; rgb.g = t2; rgb.b = t1 - t3}
          else {rgb.r = 0; rgb.g = 0; rgb.b = 0}
        }
        return {a: hsb.a,
                r: Math.round(rgb.r),
                g: Math.round(rgb.g),
                b: Math.round(rgb.b)
               };
      },
      RGBToHex = function(rgb, noAlpha) {
        var hex = [];
        if (noAlpha) {
          hex = [
            rgb.r.toString(16),
            rgb.g.toString(16),
            rgb.b.toString(16)
          ];
        } else {
          hex = [
            rgb.a.toString(16),
            rgb.r.toString(16),
            rgb.g.toString(16),
            rgb.b.toString(16)
          ];
        }
        $.each(hex, function(nr, val) {
          if (val.length == 1) {
              hex[nr] = '0' + val;
          }
        });
        return hex.join('');
      },
      HSBToHex = function(hsb, noAlpha) {
        return RGBToHex(HSBToRGB(hsb), noAlpha);
      },
      restoreOriginal = function() {
        var cal = $(this).parent();
        var self = cal.data('colorpicker');
        var col = self.origColor;
        cal.data('colorpicker').color = col;
        fillRGBFields(col, cal.get(0));
        fillHexFields(col, cal.get(0));
        fillHSBFields(col, cal.get(0));
        setSelector(col, cal.get(0));
        setHue(col, cal.get(0));
        setNewColor(col, cal.get(0));
      },
      setImg = function(img, src) {
// I think we do not need this - however I leave it in for the case that we need
// it in the end anyways.
//          if (isLessThanIE7 && src.indexOf('colorpicker_button.gif') != -1) {
//            img.attr('pngSrc', src);
//            img.css({
//              backgroundImage: 'none',
//              filter: 'progid:DXImageTransform.Microsoft.' +
//                      'AlphaImageLoader(src=\'' + src +
//                      '\', sizingMethod=\'scale\')' });
//          } else {
            img.css({ backgroundImage: 'url(' + src + ')' });
//          }
        };
        return {
          init: function(opt) {
              opt = $.extend({}, defaults, opt || {});
              if (typeof opt.color == 'string') {
                opt.color = HexToHSB(opt.color);
              } else if (typeof(opt.color.r) != 'undefined' &&
                         typeof(opt.color.g) != 'undefined' &&
                         typeof(opt.color.b) != 'undefined') {
                opt.color = RGBToHSB(opt.color);
              } else if (typeof(opt.color.h) != 'undefined' &&
                         typeof(opt.color.s) != 'undefined' &&
                         typeof(opt.color.b) != 'undefined') {
                opt.color = fixHSB(opt.color);
              } else {
                return this;
              }
              return this.each(function() {
                if (!$(this).data('colorpickerId')) {
                  var options = $.extend({}, opt);
                  var myTpl = '';
                  var myButton = '';
                  if (options.alpha) {
                    myTpl = tpla;
                    myButton =
                      '<span class="' + options.buttonStyle + '">' +
                      '<span class="' + options.buttonStyle + 'Color">' +
                      '</span>' +
                      '<span class="' + options.buttonStyle + 'Alpha">' +
                      '</span>' +
                      '<span class="' + options.buttonStyle + 'Image">' +
                      '</span></span>';
                    this.alpha = true;
                  } else {
                    myTpl = tpl;
                    myButton =
                      '<span class="' + options.buttonStyle + '">' +
                      '<span class="' + options.buttonStyle + 'Color">' +
                      '</span>' +
                      '<span class="' + options.buttonStyle + 'Image">' +
                      '</span></span>';
                    this.alpha = false;
                  }
                  // Append the palette if needed.
                  if (options.palette) {
                    for (var i = 0; i < numberPaletteEntries; i++) {
                      myTpl += palette;
                    }
                  }
                  // And terminate the list.
                  myTpl += '</div>';
                  options.origColor = opt.color;
                  var id = 'colorpicker_' + parseInt(Math.random() * 1000);
                  $(this).data('colorpickerId', id);
                  var cal = $(myTpl).attr('id', id);
                  if (options.flat) {
                    cal.appendTo(this).show();
                  } else {
                    $(this).html(myButton);
                    // Note: We append this to the main page.
                    cal.appendTo(document.body);
                  }
                  if (!this.alpha) {
                    // The alpha channel is opaque when no alpha is used.
                    options.color.a = 255;
                  }
                  if (!options.palette) {
                    if (this.alpha) {
                      cal.addClass('colorPicker_backgroundRGBA');
                    }
                  } else {
                    // Modify the size of the panel.
                    cal.css('width', '372px').addClass(
                        'colorPicker_backgroundRGB' + (this.alpha ? 'A' : '') +
                        'WithPanel');
                    var colors = cal.find('.colorpicker_palette');
                    for (var i = 0; i < numberPaletteEntries; i++) {
                      var element = colors.eq(i);
                      // Set the location of the button.
                      element.css({
                        top: i * 10 + 12
                      });
                      // Determine the color to  use.
                      var c = RGBToHSB({
                        b: (i & 1) ? 255 : ((i & 8) ? 128 : 0),
                        g: (i & 2) ? 255 : ((i & 8) ? 128 : 0),
                        r: (i & 4) ? 255 : ((i & 8) ? 128 : 0),
                        a: 255
                      });
                      if (options.paletteColors[i]) {
                        if (typeof options.paletteColors[i] == 'string') {
                          c = HexToHSB(options.paletteColors[i]);
                        } else if (typeof(options.paletteColors[i].r) !=
                                     'undefined' &&
                                   typeof(options.paletteColors[i].g) !=
                                     'undefined' &&
                                   typeof(options.paletteColors[i].b) !=
                                     'undefined') {
                          c = RGBToHSB(options.paletteColors[i]);
                        } else if (typeof(options.paletteColors[i].h) !=
                                     'undefined' &&
                                   typeof(options.paletteColors[i].s) !=
                                     'undefined' &&
                                   typeof(options.paletteColors[i].b) !=
                                     'undefined') {
                          c = fixHSB(options.paletteColors[i]);
                        }
                      }
                      // Set the color
                      element.find('.colorpicker_paletteColor').css({
                         backgroundColor: '#' + HSBToHex(c, true)
                      });
                      // Set the alpha
                      element.find('.colorpicker_paletteColor').css({
                         opacity: c.a / 255
                      });
                      // Set the action function to call when the user presses
                      // it. Since there is no closure, we have to pass the
                      // parameters via a datastructre.
                      element.bind('click', {c: c, cal: cal}, function(e) {
                        setNewColor(e.data.c, e.data.cal);
                      });
                    }
                  }
                  if (options.document != document) {
                    // If we are running inside an iFrame, we assume that we
                    // are running in 'Studio' and therefore a special Earth3D
                    // view is active. In order to have our colorpicker punching
                    // a hole into the 3D view, we have to make the entire.
                    // dialog opaque.
                    cal.css('background-color', '#a0a0a0');
                  }
                  options.fields = cal.find('input')
                                     .bind('keyup', keyDown)
                                     .bind('change', change)
                                     .bind('blur', blur)
                                     .bind('focus', focus);
                  cal.find('span').bind('mousedown', downIncrement).end()
                    .find('>div.colorpicker_current_color')
                      .bind('click', restoreOriginal);
                  options.selector = cal.find('div.colorpicker_color')
                    .bind('mousedown', downSelector);
                  options.selectorIndic = options.selector.find('div div');
                  options.el = this;
                  options.hue = cal.find('div.colorpicker_hue div');
                  cal.find('div.colorpicker_hue')
                    .bind('mousedown', downHue);
                  options.newColor = cal.find(
                    'span.colorpicker_new_color' + (this.alpha ? 'A' : ''));
                  options.currentColor = cal.find(
                    'span.colorpicker_current_color' + (this.alpha ? 'A' : ''));

                  // Remember the button.
                  options.button = $(this).find('span span:first');
                  // And initialize the color.
                  var color = HSBToHex(options.origColor, true);
                  options.button.css('backgroundColor', '#' + color);
                  if (options.alpha) {
                    options.buttonAlpha = $(this).find(
                        'span span:.' + options.buttonStyle + 'Alpha');
                    options.buttonAlpha.css('opacity',
                                            1.0 - options.origColor.a / 255);
                  }

                  cal.data('colorpicker', options);
                  if (options.livePreview) {
                    cal.find('div.colorpicker_revert')
                      .bind('mouseenter', enterRevert)
                      .bind('mouseleave', leaveRevert)
                      .bind('click', clickRevert);
                  } else {
                    // Remove the button from the UI.
                    cal.find('div.colorpicker_revert').css({
                      display: 'none'
                    });
                  }
                  cal.find('div.colorpicker_submit')
                    .bind('mouseenter', enterSubmit)
                    .bind('mouseleave', leaveSubmit)
                    .bind('click', clickSubmit);
                  fillRGBFields(options.color, cal.get(0));
                  fillHSBFields(options.color, cal.get(0));
                  fillHexFields(options.color, cal.get(0));
                  setHue(options.color, cal.get(0));
                  setSelector(options.color, cal.get(0));
                  setCurrentColor(options.color, cal.get(0));
                  setNewColor(options.color, cal.get(0));
                  if (options.flat) {
                    cal.css({
                      position: 'relative',
                      display: 'block'
                    });
                  } else {
                    $(this).bind(options.eventName, show);
                  }
                }
              });
            },
            showPicker: function() {
              return this.each(function() {
                if ($(this).data('colorpickerId')) {
                  show.apply(this);
                }
              });
            },
            hidePicker: function() {
              return this.each(function() {
                if ($(this).data('colorpickerId')) {
                  $(document)
                    .find('#' + $(this).data('colorpickerId')).hide();
                }
              });
            },
            setColor: function(col) {
              if (typeof col == 'string') {
                col = HexToHSB(col);
              } else if (typeof(col.r) != 'undefined' &&
                         typeof(col.g) != 'undefined' &&
                         typeof(col.b) != 'undefined') {
                col = RGBToHSB(col);
              } else if (typeof(col.h) != 'undefined' &&
                         typeof(col.s) != 'undefined' &&
                         typeof(col.b) != 'undefined') {
                col = fixHSB(col);
              } else {
                return this;
              }
              return this.each(function(){
                // This is more then the name -it is a jQuery object from the
                // correct page(!). So we can keep the colorpickerId there.
                if ($(this).data('colorpickerId')) {
                  // Using the 'this' element, we can get the owning page and
                  // from there we can get the colorpicker and then the rest.
                  var cal = $(document)
                    .find('#' + $(this).data('colorpickerId'));
                  var self = cal.data('colorpicker');
                  self.color = col;
                  self.origColor = col;
                  fillRGBFields(col, cal.get(0));
                  fillHSBFields(col, cal.get(0));
                  fillHexFields(col, cal.get(0));
                  setHue(col, cal.get(0));
                  setSelector(col, cal.get(0));
                  setCurrentColor(col, cal.get(0));
                  setNewColor(col, cal.get(0));
                  // Set the thumbnail accordingly.
                  var color = HSBToHex(col, true);
                  self.button.css('backgroundColor', '#' + color);
                  if (self.alpha) {
                    self.buttonAlpha.css('opacity', 1.0 - col.a / 255);
                  }
                }
              });
            }
        };
    }();
    $.fn.extend({
        ColorPicker: ColorPicker.init,
        ColorPickerHide: ColorPicker.hidePicker,
        ColorPickerShow: ColorPicker.showPicker,
        ColorPickerSetColor: ColorPicker.setColor
    });
})(jQuery);
