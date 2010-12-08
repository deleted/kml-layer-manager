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

"""A set of handlers to manage resources."""

import cgi
import httplib
import os
import urllib
from django.utils import simplejson as json
from google.appengine import runtime
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import handlers.base
import model
import settings
import util


class ResourceHandler(blobstore_handlers.BlobstoreUploadHandler,
                      handlers.base.PageHandler):
  """A handler to upload and delete resources."""

  PERMISSION_REQUIRED = model.Permission.RESOURCES
  FORM_TEMPLATE = 'resource'
  ASSOCIATED_MODEL = model.Resource

  def ShowForm(self, layer):
    """Displays a resource upload and deletion form."""
    layer_id = layer.key().id()
    upload_url = blobstore.create_upload_url('/resource-create/%d' % layer_id)
    return {'upload_url': upload_url}

  def ShowRaw(self, layer):
    """Displays the result of Create(), as passed to it in the query string.

    The results are written in 5 lines:
      1. Status: BAD_REQUEST (400) if the "error" query argument is set.
         Otherwise OK (200).
      2. Result ID: The contents of the "result" query argument. This should be
         the ID(s) of the created resource(s) if any were created successfully.
         May be empty if creation failed.
      3. Error Message: The contents of the "error" query argument. May be empty
         if creation succeeded.
      4. Single Upload URL: A new upload URL that a user can use to upload
         another resource.
      5. Bulk Upload URL: A new upload URL that a user can use to bulk upload
         multiple resources.

    The status code is written out because on the client side, upload forms have
    to be submitted into an iframe and as a result the normal status code cannot
    be accessed through JS.

    GET Args:
      result: The ID of the created resource.
      error: An error message. Ignored if result is set.

    Args:
      layer: The layer to which the created resource belongs.
    """
    error = self.request.get('error')
    result = self.request.get('result')

    layer_id = layer.key().id()
    single_url = blobstore.create_upload_url('/resource-create/%d' % layer_id)
    bulk_url = blobstore.create_upload_url('/resource-bulk/%d' % layer_id)

    if error:
      status = httplib.BAD_REQUEST
    else:
      status = httplib.OK
    self.response.set_status(status)
    self.response.out.write(status)
    self.response.out.write('\n')
    self.response.out.write(cgi.escape(result or ''))
    self.response.out.write('\n')
    self.response.out.write(cgi.escape(error or ''))
    self.response.out.write('\n')
    self.response.out.write(cgi.escape(single_url))
    self.response.out.write('\n')
    self.response.out.write(cgi.escape(bulk_url))

  def ShowList(self, layer):
    """Lists all resources in the given layer of a specified type.

    Writes out a JSON list of resources, each item including the name and URL of
    the resource. If no type is specified, each item also has a type property
    with its type.

    GET Args:
      type: The type of resources to list. If specified, must be one of
          model.Resource.TYPES. If not specified, all resources are listed,
          along with their types.

    Args:
      layer: The layer whose resources are to be listed.
    """
    requested_type = self.request.get('type', None)
    if requested_type and requested_type not in model.Resource.TYPES:
      raise util.BadRequest('Invalid resource type.')
    resources_to_write = []
    for resource in layer.resource_set:
      if requested_type in (resource.type, None):
        info = {'id': resource.key().id(), 'url': resource.GetURL(),
                'name': resource.filename}
        if not requested_type: info['type'] = resource.type
        resources_to_write.append(info)
    self.response.out.write(json.dumps(resources_to_write))

  def Create(self, layer):
    """Handles resource creation, including blobstore uploads.

    Since blob upload handlers must use a redirect rather than write the
    response out, a redirect is issued to /resource-raw/{layer_id} with an error
    or result query argument. The result is the ID of the new resource.

    POST Args:
      type: The type of the resource. Must be one of model.Resource.TYPES. If
          "image", the upload is validated as an image. If it is "icon", the
          upload is validated as an icon. Icons larger than
          settings.MAX_ICON_SIZE pixels in either dimension are rejected.
      filename: A filename for the resource. If a file was uploaded, and type is
          not model_in_kmz, this can be left unspecified. In the case of
          model_in_kmz resources, the filename must be the name of the COLLADA
          model file inside the KMZ.
      url: The URL of an external resource. If this is specified, nothing should
          be uploaded.
      file: An uploaded data file.

    Args:
      layer: The layer to which the new resource will belong.
    """
    try:
      uploaded_file = self.get_uploads('file')
      if uploaded_file:
        uploaded_file = uploaded_file[0]
      else:
        uploaded_file = None
      resource_id = self._CreateResource(layer,
                                         self.request.get('type'),
                                         self.request.get('filename'),
                                         self.request.get('url'),
                                         uploaded_file)
    except util.BadRequest, e:
      self._DeleteBlobs(self.get_uploads())
      redirect_args = 'error=%s' % e
    else:
      redirect_args = 'result=%d' % resource_id
    self.redirect('/resource-raw/%d?%s' % (layer.key().id(), redirect_args))
    raise util.RequestDone(redirected=True)

  def BulkCreate(self, layer):
    """Handles bulk resource creation, including blobstore uploads.

    Makes sure either an external URL was specified or a valid file was uploaded
    for each entry and creates a new Resource instance for that blob or URL.

    Since blob upload handlers must use a redirect rather than write the
    response out, a redirect is issued to /resource-raw/{layer_id} with an error
    and result query argument. The result is an ordered comma-separated list of
    IDs of the new resources. The list may have fewer elements than the number
    of specified resources if an error was encountered during resource creation.

    POST Args:
      Receives any number of resource descriptions, where each resource is
      described by the same type/filename/url/file paramaters that are mentioned
      in Create(). Parameter names should have the number of the resource
      appended, with the numbering starting from 0. For example the first
      resource may be described by type0, filename0 and url0, the second by
      type1, filename1 and file1, etc.

    Args:
      layer: The layer to which the new resources will belong.
    """
    uploads = self.get_uploads()
    index = 0
    created_resource_ids = []
    error = None
    try:
      while True:
        resource_type = self.request.get('type%d' % index)
        name = self.request.get('filename%d' % index)
        url = self.request.get('url%d' % index)
        blob = self.get_uploads('file%d' % index)
        if blob: blob = blob[0]

        if not resource_type:
          # No more resources.
          break

        try:
          new_id = self._CreateResource(layer, resource_type, name, url, blob)
        except util.BadRequest, e:
          # A failed resource. Delete unprocessed ones.
          self._DeleteBlobs(uploads)
          error = 'Resource %d: %s' % (index, e)
          break
        created_resource_ids.append(new_id)

        if blob in uploads:
          uploads.remove(blob)

        index += 1
    except runtime.DeadlineExceededError:
      self._DeleteBlobs(uploads)
      error = 'Ran out of time.'
      # We still want to write out the resource IDs and issue a redirect.

    result = ','.join(str(i) for i in created_resource_ids)
    if error:
      self.redirect('/resource-raw/%s?result=%s&error=%s' %
                    (layer.key().id(), result, urllib.quote(error)))
    else:
      self.redirect('/resource-raw/%s?result=%s' % (layer.key().id(), result))
    raise util.RequestDone(redirected=True)

  def Delete(self, layer):
    """Deletes a resource.

    If anything in the datastore references this resource, returns an error.

    POST Args:
      resource_id: The ID of the resource to delete.

    Args:
      layer: The layer to which the resource to delete belongs.
    """
    resource_id = self.request.get('resource_id')
    resource = util.GetInstance(model.Resource, resource_id, layer)
    if _IsResourceReferenced(resource):
      raise util.BadRequest('A reference to this resource was found.')
    # NOTE: May leave an inaccessible orphan blob if delete fails.
    blob = resource.blob
    resource.delete()
    if blob: blob.delete()

  @staticmethod
  def _CreateResource(layer, resource_type, name, url, blob):
    """Creates a resource from the specified parameters.

    Args:
      layer: The layer to which the new resources will belong.
      resource_type: The type fo the resource, one of model.Resource.TYPES.
      name: The name of the new resource, optional for non-KMZ uploads.
      url: An external URL pointing to the resource's data. Either this or blob
          must be specified.
      blob: The BlobInfo of an uploaded file to assign to the new resource.

    Returns:
      The ID of the new resource.

    Raises:
      util.BadRequest: On invalid input.
    """

    if resource_type not in model.Resource.TYPES:
      raise util.BadRequest('Invalid resource type. Must be one of: %s.' %
                            model.Resource.TYPES)

    if url:
      if not name:
        raise util.BadRequest('No filename provided for an external resource.')
      resource = model.Resource(layer=layer, filename=name,
                                type=resource_type, external_url=url)
    elif blob:
      if resource_type in ('image', 'icon'):
        if not _IsImage(blob):
          raise util.BadRequest('The uploaded file is not a valid image.')

        if resource_type == 'icon':
          size = _TryGetImageSize(blob)
          if size is None or (size[0] > settings.MAX_ICON_SIZE or
                              size[1] > settings.MAX_ICON_SIZE):
            raise util.BadRequest('The uploaded image is too large to be an '
                                  'icon.')
      elif resource_type == 'model_in_kmz' and not name:
        raise util.BadRequest('A filename must be supplied when uploading a '
                              'model packed into a KMZ archive.')
      if not name:
        name = blob.filename
      resource = model.Resource(layer=layer, filename=name,
                                type=resource_type, blob=blob)
    else:
      raise util.BadRequest('Neither URL nor file specified.')
    resource.put()
    return resource.key().id()

  @staticmethod
  def _DeleteBlobs(blobs):
    """Safely deletes the specified blobs."""
    for blob in blobs:
      # pylint: disable-msg=W0702
      # Catching all exceptions here because on the dev server, the upload
      # blobs are sometimes locked, and may throw exceptions of uncertain type
      # (e.g. on Windows it's a WindowsError, on other systems it is likely to
      # be something else).
      try:
        blob.delete()
      except:
        if not os.environ['SERVER_SOFTWARE'].startswith('Development'):
          raise


def _IsImage(blob):
  """Checks if a blob contains image data."""
  try:
    image = images.Image(blob_key=str(blob.key()))
    # Force image to load.
    image.horizontal_flip()
    image.execute_transforms()
  except (images.BadImageError, images.NotImageError):
    return False
  except images.LargeImageError:
    pass
  return True


def _TryGetImageSize(blob):
  """Attempts to find the width and height of an image stored in blobstore.

  An image constructed from a blobstore blob does not fetch the data unless
  a transformation is applied to it and as a result does not provide the width
  and height attributes. Therefore we apply a no-op transformation to force
  the data to be fetched then return the newly-initialized width and height.
  However, images that are larger than 1MB in JPEG form cannot be returned by
  the transformer, and therefore this function may fail.

  Args:
    blob: The blob containing the image data.

  Returns:
    If the transformation succeeded, returns a 2-tuple of the image's width
    and height. Otherwise returns None.
  """
  image = images.Image(blob_key=str(blob.key()))
  try:
    image.crop(0.0, 0.0, 1.0, 1.0)
    data = image.execute_transforms(output_encoding=images.JPEG)
    transformed_image = images.Image(image_data=data)
    return transformed_image.width, transformed_image.height
  except (images.TransformationError, images.LargeImageError):
    return None


def _IsResourceReferenced(resource):
  """Checks whether the resource is referenced by any model in the database."""
  # All references create backreferences named *_set, except containers,
  # which have no backreference (due to circular dependency issues).
  for property_name in dir(resource):
    if (property_name.endswith('_set') and
        getattr(resource, property_name).get()):
      return True
  return bool(resource.layer.folder_set.filter('icon', resource).get() or
              resource.layer.link_set.filter('icon', resource).get() or
              resource.layer.icon == resource)
