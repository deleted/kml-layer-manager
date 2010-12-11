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

from distutils.core import setup

setup(name='layermanager_client',
      version='0.1.0',
      py_modules=['layermanager_client'],
      scripts=['layermanager_download.py'],
      url='http://code.google.com/p/kml-layer-manager/',
      maintainer='Matt Hancher',
      maintainer_email='mdh@google.com',
      license='Apache License, Version 2.0',
      description='Client library for the KML Layer Manager',
      long_description='''This is a simple library for interacting with a KML Layer Manager
instance from your own client-side Python scripts.''',
      )
