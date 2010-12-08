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
 * @fileoverview External identifier declarations for use with a JS compiler.
 */

// Google AJAX API identifiers.
var google;

// Dynamically loaded libraries.
var jQuery;

// Main namespace, defined inline in base.html.
var layermanager;

// Browser-defined objects and functions.
var window;
var JSON;
var console;
function alert(message) {};
function confirm(question) {};
function prompt(question) {};

// Language-defined value constants.
var Math;
var parseInt;
var parseFloat;
var undefined;
var arguments;

// Browser-defined object types.
/**
 * @constructor
 * @param {*} opt_source
 * @return {string}
 */
function String(opt_source) {}
/**
 * @constructor
 * @param {*} opt_source
 * @return {boolean}
 */
function Boolean(opt_source) {}
/**
 * @constructor
 * @param {*} regex
 * @param {*} flags
 * @return {!RegExp}
 */
function RegExp(regex, flags) {}
/**
 * @constructor
 * @param {?} year
 * @param {?} month
 * @param {?} day
 * @param {?} hours
 * @param {?} minutes
 * @param {?} seconds
 * @param {?} milliseconds
 * @return {string}
 */
function Date(year, month, day, hours, minutes, seconds, milliseconds) {}

/** @constructor */
function Element() {}
/** @constructor */
function Window() {}
