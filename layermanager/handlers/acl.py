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

"""A simple global application permissions editing page."""

import os
from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
import model


class ACLHandler(webapp.RequestHandler):
  """A form to edit global application permissions."""

  def get(self):  # pylint: disable-msg=C6409
    """Displays a list of authenticated users and a from to edit them."""
    template_path = os.path.join(os.path.dirname(__file__), '..',
                                 'html_templates', 'acl.html')
    template_args = {'users': model.AuthenticatedUser.all()}
    self.response.out.write(template.render(template_path, template_args))

  def post(self):  # pylint: disable-msg=C6409
    """Adds or deletes an authenticated user then displays the ACL form."""
    user = users.User(self.request.get('email'))
    action = self.request.get('action')
    if action == 'Delete':
      entry = model.AuthenticatedUser.all().filter('user', user).get()
      if entry:
        entry.delete()
    elif action == 'Add':
      model.AuthenticatedUser(user=user).put()
    else:
      self.error(400)
      return
    self.get()
