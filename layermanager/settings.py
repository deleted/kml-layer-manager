#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Basic configuration constants for the KML Layer Manager."""


##############################  Authentication  ################################
# Whether to use the global ACL system to protect the whole app. If False,
# anyone can log into the app and create their own layer. Per-layer permissions
# are not affected by this flag.
USE_GLOBAL_ACL = True

#############################  Google JS API Keys  #############################
# Google Maps JS API keys for all the hosts on which this app runs.
#
# Be sure to generate an API key for your domain name and add it to this list.
# You can obtain an API key from http://code.google.com/apis/maps/signup.html
JS_API_KEYS = {
    'localhost:8080':
      ('ABQIAAAAm9PBg-S-obmCjikyebMgRBTwM0brOpm-All5BF6PoaKBxRWWERSVVyWvub6hAbb'
       'C2LLk61PiMjv4sQ'),
      'nasa-kml-layerman.appspot.com': 'ABQIAAAAmppN0YOeT1tgPVlsTGO4pBSToPO2M3BBWdafoiJxmDc0JYTkyhSVmLyjyqIZ0lKygfvu40kAHdE9SA',
}

#################################  MIME Types  #################################
# The MIME type to use when serving generated KML files.
KML_MIME_TYPE = 'application/vnd.google-earth.kml+xml'
# The MIME type to use when serving KMZ blobs.
KMZ_MIME_TYPE = 'application/vnd.google-earth.kmz'
# The MIME type to use when serving COLLADA model blobs.
COLLADA_MIME_TYPE = 'application/collada+xml'

################################  Image Sizes  #################################
# The maximum width or height of an image, in pixels, to be allowed as an icon.
MAX_ICON_SIZE = 64
# The minimum height or width, in pixels, accepted in thumbnailing requests.
MIN_THUMBNAIL_SIZE = 16
# The maximum height or width, in pixels, accepted in thumbnailing requests.
MAX_THUMBNAIL_SIZE = 512

#########################  Handler Name-Action Tables  #########################
# Commands that use GET requests mapped to the methods that implement them.
GET_COMMANDS = {
    'form': 'ShowForm',
    'raw': 'ShowRaw',
    'list': 'ShowList'
}
# Commands that use POST requests mapped to the methods that implement them.
POST_COMMANDS = {
    'create': 'Create',
    'delete': 'Delete',
    'update': 'Update',
    'move': 'Move',
    'bulk': 'BulkCreate'
}

###########################  Default Baker Settings  ###########################
# The default soft maximum for the number of entities per Division. Used when a
# layer does not specify division size.
DEFAULT_DIVISION_SIZE = 100
# How much bigger a division is allowed to grow to avoid extra subdivision
# steps, relative to the soft maximum set by the layer or DEFAULT_DIVISION_SIZE.
# If soft maximum = 42, growth limit = 0.5, then hard maximum = 42+42*0.5 = 63.
DIVISION_SIZE_GROWTH_LIMIT = 0.5
# The number of seconds to wait between two successive baker monitoring tasks.
BAKER_MONITOR_DELAY = 5

#########################  Dynamic Balloon Placeholder  ########################
# The placeholder ID for flyTo links that is used when serving dynamic balloons.
BALLOON_LINK_PLACEHOLDER = 'KML_LAYER_MANAGER_LINK_PLACEHOLDER'
