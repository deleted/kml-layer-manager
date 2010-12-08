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

"""The layer permissions editing page of the KML Layer Manager."""

import itertools
import operator
from google.appengine.api import users
from google.appengine.ext import db
import handlers.base
import model
import util


class PermissionHandler(handlers.base.PageHandler):
  """A form to add, remove and edit permissions."""

  PERMISSION_REQUIRED = model.Permission.MANAGE
  FORM_TEMPLATE = 'permission'

  def ShowForm(self, layer):
    """Displays a permission editing form.

    Retrieves permissions to show on the form. The permissions are then grouped
    into a list by user. Each entry is a dictionary including the user's email
    and a mapping of permission type to a Boolean indicating whether the user
    has that permission type or not. Example:
      [
        {'email': 'foo@example.com',
         'access': True, 'resources': False, ...},
        {'email': 'bar@example.com',
         'access': False, 'resources': True, ...},
        ...
      ]

    Args:
      layer: The layer whose permissions to display.

    Returns:
      A one-item dictionary mapping 'permissions' to the list of permissions
      calculated as shown above.
    """

    permissions = []
    raw_permissions = list(layer.permission_set.order('user'))
    grouped = itertools.groupby(raw_permissions, operator.attrgetter('user'))
    for user, user_permissions in grouped:
      user_permissions = [i.type for i in user_permissions]
      permission = {'email': user.email()}
      for permission_type in model.Permission.TYPES:
        permission[permission_type] = permission_type in user_permissions
      permissions.append(permission)

    return {'permission_types': model.Permission.TYPES,
            'permissions': permissions}

  def Update(self, layer):
    """Updates the permissions for the specified layer.

    If permissions are consistent, they are written to the data store and an
    empty response with the HTTP status NO_CONTENT is sent. Otherwise an error
    message is written and the HTTP status BAD_REQUEST is sent.

    POST Args:
      users: A list of user emails.
      For each user, zero or more arguments specifying permissions, each named
          in the form email_permissiontype, where email is the user's email and
          permissiontype is one of the constants defined in model.Permission.
          For each user, permissions for which the respective permission
          argument exists are granted, and permission for which the respective
          argument does not exist are withdrawn. The actual values of the
          permission arguments are ignored. For example, the following:
            users = a@b.c
            users = d@e.f
            users = g@h.i
            a@b.c_access = 1
            a@b.c_entities = 1
            a@b.c_styles = 1
            d@e.f_access = 1
          will result in g@h.i losing all their permissions (if they had any),
          d@e.f having only the access permission, and a@b.c having the access,
          entities and styles permissions. Their permission prior to the change
          don't matter.
    Args:
      layer: The layer whose permissions are being updated.
    """
    user_emails = self.request.get_all('users')
    permissions_to_write = []
    layer_has_manager = False

    for email in user_emails:
      permissions = {}
      permissions_count = 0
      for permission_type in model.Permission.TYPES:
        permission_exists = self.request.get('%s_%s' % (email, permission_type))
        permissions[permission_type] = bool(permission_exists)
        if permission_exists:
          permissions_count += 1
          permission = model.Permission(user=users.User(email), layer=layer,
                                        type=permission_type, parent=layer)
          permissions_to_write.append(permission)
          if permission_type == model.Permission.MANAGE and permission_exists:
            layer_has_manager = True

      # Check for inconsistencies.
      if permissions_count and not permissions[model.Permission.ACCESS]:
        raise util.BadRequest('User %s cannot have edit permissions without '
                              'having an access permission.' % email)
      elif (permissions_count < len(model.Permission.TYPES) and
            permissions[model.Permission.MANAGE]):
        raise util.BadRequest('User %s cannot have a manage permission without '
                              'having all other permissions.' % email)

    if not layer_has_manager:
      raise util.BadRequest('The layer must have at least one manager.')

    db.run_in_transaction(_UpdatePermissions, layer, user_emails,
                          permissions_to_write)


def _UpdatePermissions(layer, user_emails, permissions):
  """Update a layer's permissions for the specified users.

  Deletes all permissions for the specified layer for the specified users,
  then writes the permissions objects in the permissions argument. This
  function should be run in a transaction.

  Args:
    layer: The layer object for which the permissions should be updated.
    user_emails: A list of emails of users whose permissions should be
        cleared before applying the new permission set.
    permissions: A list of Permission objects to be written. These are not
        checked against either the layer or the users. The caller is responsible
        for verifying these permissions before calling this function.
  """
  for permission in layer.permission_set.ancestor(layer):
    if permission.user.email() in user_emails:
      permission.delete()
  for permission in permissions:
    permission.put()
