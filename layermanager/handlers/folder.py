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

"""The folders organizing page of the KML Layer Manager."""

from google.appengine import runtime
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors
import handlers.base
import model
import util


class FolderHandler(handlers.base.PageHandler):
  """A form to manage folders and move entities around."""

  PERMISSION_REQUIRED = model.Permission.MANAGE
  FORM_TEMPLATE = 'folder'
  ASSOCIATED_MODEL = model.Folder

  # pylint: disable-msg=E1002
  # No, lint, this is a new style class.
  def ShowRaw(self, layer):
    """Writes out a JSON representation of the folder.

    GET Args:
      id: The ID of the folder.
      nocontents: If supplied (regardless of value), the folder's contents are
          not included in the output.

    Args:
      layer: The layer to which the folder belongs.
    """
    if self.request.get('nocontents', None) is None:
      folder = util.GetInstance(model.Folder, self.request.get('id'), layer)
      contents = [(i.key().id(), type(i).__name__)
                  for i in folder.GetSortedContents()]
    else:
      contents = []
    handlers.base.PageHandler.ShowRaw(self, layer, contents=contents)

  def Create(self, layer):
    """Creates a new folder.

    POST Args:
      Expects POST arguments with the same names as the model.Folder properties.
      For reference properties, the expected value is the ID of the referenced
      instance.

    Args:
      layer: The layer to which the new folder will belong.
    """
    try:
      fields = GetContainerFields(self.request, layer)
      folder = model.Folder(layer=layer, **fields)
      layer.ClearCache()
      folder.put()
      folder.GenerateKML()  # Build cache.
    except (db.BadValueError, TypeError, ValueError), e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(folder.key().id())

  def Update(self, layer):
    """Updates a folder's properties.

    POST Args:
      folder_id: The ID of the folder to modify.
      The rest of the arguments are the same as for Create().

    Args:
      layer: The layer to which the folder to update belongs.
    """
    UpdateContainer(self.request, layer)

  def Move(self, layer):
    """Moves the specified folders, links or entities into the specified folder.

    The specified items are added to the specified folder with sequential
    indices starting with 0. If any of the items already in the folder are not
    specified in the request, their indices are not updated.

    Although unlikely, it is possible that this function will fail to move all
    the contents. To address this, it writes out a list of contents that have
    been moved successfully, in the "type,id" format, one per line. The client
    is responsible for retrying failed attempts.

    POST Args:
      parent: The ID of the folder to move the objects into, or "" to move the
          contents into the layer root.
      contents[]: A folder, entity or link to move, in the form type,id. May
          occur multiple times. The order is preserved. Example:
          ?parent=1&contents[]=entity,5&contents[]=link,3&contents[]=folder,9

    Args:
      layer: The layer to which all the objects involed in the move belong.
    """
    parent = self.request.get('parent') or None
    if parent:
      parent = util.GetInstance(model.Folder, parent, layer)
    contents = self.request.get_all('contents[]')
    if not contents:
      raise util.BadRequest('No contents specified.')

    content_records = []
    record_counter = 0
    for item_argument in contents:
      try:
        item_type, item_id = item_argument.split(',')
        item_id = int(item_id)
      except (TypeError, ValueError):
        raise util.BadRequest('Invalid content argument specified.')
      if item_type not in ('entity', 'folder', 'link'):
        raise util.BadRequest('Invalid content type specified.')
      item = util.GetInstance(getattr(model, item_type.title()), item_id, layer)
      content_records.append((item, record_counter))
      record_counter += 1

    layer.ClearCache()
    for item, index in content_records:
      item.folder = parent
      item.folder_index = index
      item.put()
      item_type = item.__class__.__name__.lower()
      self.response.out.write('%s,%d\n' % (item_type, item.key().id()))

  def Delete(self, layer):
    """Deletes a folder.

    All entities inside this folder have their folder property set to None,
    effectively moving them to the layer root.

    POST Args:
      folder_id: The ID of the folder to delete.

    Args:
      layer: The layer to which the folder to delete belongs.
    """
    layer.ClearCache()
    _DeleteFolder(layer, self.request.get('folder_id'))


class FolderQueueHandler(handlers.base.PageHandler):
  """A handler to continue folder deletion after timing out."""

  PERMISSION_REQUIRED = None

  def Delete(self, layer):
    """Deletes the specified folder and move all its contents out."""
    _DeleteFolder(layer, self.request.get('folder_id'))


def _DeleteFolder(layer, folder_id):
  """Deletes the specified folder and move all its contents out."""
  folder = util.GetInstance(model.Folder, folder_id, layer)
  try:
    for entity in folder.entity_set:
      entity.folder = None
      entity.put()
    folder.delete()
  except (runtime.DeadlineExceededError, db.Error,
          apiproxy_errors.OverQuotaError):
    # Schedule continuation.
    taskqueue.add(url='/folder-continue-delete/%d' % layer.key().id(),
                  params={'folder_id': folder_id})


def GetContainerFields(request, layer):
  """Collects container fields from a request."""
  icon = request.get('icon')
  icon = util.GetInstance(model.Resource, icon, layer, required=False)
  if icon and icon.type != 'icon':
    raise util.BadRequest('Invalid (non-icon) resource specified.')

  folder = request.get('folder')
  folder = util.GetInstance(model.Folder, folder, layer, required=False)
  folder_index = request.get('folder_index', None)
  if folder_index is not None: folder_index = int(folder_index)

  region = request.get('region')
  region = util.GetInstance(model.Region, region, layer, required=False)

  return {
      'icon': icon,
      'folder': folder,
      'folder_index': folder_index,
      'region': region,
      'name': request.get('name', None),
      'description': request.get('description', None),
      'item_type': request.get('item_type', None),
      'custom_kml': request.get('custom_kml', None)
  }


def UpdateContainer(request, layer, id_field='folder_id',
                    container_model=model.Folder):
  """Updates a container instance with fields specified in the request."""
  container_id = request.get(id_field)
  instance = util.GetInstance(container_model, container_id, layer)
  try:
    for property_name in container_model.properties():
      value = request.get(property_name, None)
      if value == '':  # pylint: disable-msg=C6403
        setattr(instance, property_name, None)
      elif value is not None:
        if property_name == 'icon':
          icon = request.get('icon')
          icon = util.GetInstance(model.Resource, icon, layer, required=False)
          if icon and icon.type != 'icon':
            raise util.BadRequest('Invalid (non-icon) resource specified.')
          instance.icon = icon
        elif property_name == 'region':
          region = util.GetInstance(model.Region, value, layer)
          if region:
            instance.region = region
          else:
            raise db.BadValueError('Invalid region specified.')
        elif property_name == 'folder':
          folder = util.GetInstance(model.Folder, value, layer)
          if folder:
            instance.folder = folder
          else:
            raise db.BadValueError('Invalid folder specified.')
        elif property_name == 'folder_index':
          if value.isdigit():
            instance.folder_index = int(value)
          else:
            raise db.BadValueError('Invalid folder index specified.')
        else:
          setattr(instance, property_name, value)
    instance.ClearCache()
    instance.put()
    instance.GenerateKML()  # Rebuild cache.
  except db.BadValueError, e:
    raise util.BadRequest(str(e))
