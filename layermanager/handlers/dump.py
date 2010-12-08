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

"""A handler to serve resources and KML."""

import collections
import httplib
import re
import xml.dom.minidom
import zipfile
from google.appengine.api import images
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
import model
import settings
import util


class DumpServer(blobstore_handlers.BlobstoreDownloadHandler):
  """A handler to serve KML and resources."""

  def get(self, layer_id, typecode, object_id):  # pylint: disable-msg=C6409
    """Publicly serves a resource or KML.

    GET Args:
      compress: If set to "no", disables any KMZ compression that might
          otherwise have occurred.
      pretty: If specified when serving a KML, the KML is returned nicely
          formatted and easy for a human to read.
      resize: When serving an image or icon resource, this argument is used to
          define the larger side of a thumbnail to serve, in pixels. Must be an
          integer between settings.MIN_THUMBNAIL_SIZE and
          settings.MAX_THUMBNAIL_SIZE. Ignored for non-resources or resources
          of types other than image and icon. Resized thumbnails are always
          served as a PNG file, regardless of the format of the original blob.

    Args:
      layer_id: The ID of a layer to use if object_id is unspecified. Unused in
          all other cases.
      typecode: Specifies whether to serve a resource or a KML. "r" means
          a resource, "k" means a KML and empty means KML iff object_id is
          "root".
      object_id: The ID of the object to serve. This may be a Resource, a Layer
          or a Division, depending on the typecode parameter.
    """
    resize = self.request.get('resize', None)
    no_compress = self.request.get('compress', None) == 'no'
    pretty = 'pretty' in self.request.arguments()

    try:
      if typecode == 'r':
        self.GetResource(object_id, resize)
      elif typecode == 'k':
        division = util.GetInstance(model.Division, object_id)
        compress = division.layer.compressed and not no_compress
        self.GetKML(division, compress, pretty)
      elif not typecode and not object_id:
        layer = util.GetInstance(model.Layer, layer_id)
        if layer.auto_managed and not layer.baked:
          raise util.BadRequest('This auto-managed layer has not been baked.')
        else:
          compress = layer.compressed and not no_compress
          self.GetKML(layer, compress, pretty)
      else:
        raise util.BadRequest('Invalid typecode or object ID.')
    except util.BadRequest, e:
      self.error(httplib.BAD_REQUEST)
      self.response.out.write(str(e))

  def GetResource(self, resource_id, size=None):
    """Serves a resource blob and optionally dynamically resizes images.

    If the size paramater is not supplied, the blob is served directly. If it
    is, and the blob is an image or an icon, it is resized and served manually.
    Resized thumbnails are always served as a PNG file, regardless of the format
    of the original blob.

    No permissions are checked when serving blobs.

    Args:
      resource_id: The ID of the reource to serve. The specified resource must
          have the blob property set.
      size: The size of the larger side of the thumbnail to serve, in pixels.
          Must be an integer between settings.MIN_THUMBNAIL_SIZE and
          settings.MAX_THUMBNAIL_SIZE. Ignored for resources not of type image
          or icon.
    """
    resource = util.GetInstance(model.Resource, resource_id)
    if resource.blob:
      blob_key = resource.blob.key()
      if blobstore.get(blob_key):
        self.response.headers['Cache-Control'] = 'max-age=31557600, public'
        self.response.headers['Expires'] = 'Sat, 19 Jul 2110 22:20:03 +0000'
        if size is None or resource.type not in ('image', 'icon'):
          if resource.type == 'model':
            self.send_blob(blob_key, content_type=settings.COLLADA_MIME_TYPE)
          elif resource.type == 'model_in_kmz':
            self.send_blob(blob_key, content_type=settings.KMZ_MIME_TYPE)
          else:
            self.send_blob(blob_key)
        else:
          try:
            size = int(size)
          except ValueError:
            raise util.BadRequest('Invalid thumbnail size specified.')

          if settings.MIN_THUMBNAIL_SIZE <= size <= settings.MAX_THUMBNAIL_SIZE:
            image = images.Image(blob_key=str(blob_key))
            # Automatically keeps aspect ratio.
            image.resize(size, size)
            thumbnail = image.execute_transforms(output_encoding=images.PNG)

            if thumbnail:
              self.response.headers['Content-Type'] = 'image/png'
              self.response.out.write(thumbnail)
            else:
              # If the requested size is equal to the original size,
              # execute_transforms() returns an empty string. In that case we
              # send back the original image.
              self.send_blob(blob_key)
          else:
            raise util.BadRequest('Invalid thumbnail size specified.')
      else:
        self.error(httplib.NOT_FOUND)
    elif resource.external_url:
      self.redirect(resource.external_url, permanent=True)
    else:
      raise util.BadRequest('Invalid resource specified.')

  def GetKML(self, layer_or_division, compressed, pretty):
    """Serves a raw Layer or Division KML with the proper content type.

    Args:
      layer_or_division: The Layer or Division whose KML is to be generated.
      compressed: Whether the resulting KML should be zipped.
      pretty: Whether the resulting KML should be formatted for readability by
          humans. If specified, overrides compressed.
    """
    self.response.headers['Content-Type'] = settings.KML_MIME_TYPE
    cache = collections.defaultdict(dict)
    kml = layer_or_division.GenerateKML(cache).encode('utf8')
    if pretty:
      try:
        pretty_kml = xml.dom.minidom.parseString(kml).toprettyxml()
      except Exception, e:
        raise util.BadRequest('Could not format XML: ' + str(e))
      kml = re.sub(r'\n\s*\n', '\n', re.sub(r'\t', '  ', pretty_kml))

    if compressed and not pretty:
      self.response.headers['Content-Type'] = settings.KMZ_MIME_TYPE
      zipper = zipfile.ZipFile(self.response.out, 'w', zipfile.ZIP_DEFLATED)
      info = zipfile.ZipInfo('doc.kml')
      info.compress_type = zipfile.ZIP_DEFLATED
      info.external_attr = 0644 << 16  # Owner read/write, group/others read.
      zipper.writestr(info, kml)
      zipper.close()
    else:
      self.response.out.write(kml)
