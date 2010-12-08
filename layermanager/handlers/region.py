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

"""The region editing page of the KML Layer Manager."""

from google.appengine.ext import db
import handlers.base
import model
import util


class RegionHandler(handlers.base.PageHandler):
  """A form to create, update and delete regions."""

  PERMISSION_REQUIRED = model.Permission.ENTITIES
  FORM_TEMPLATE = 'region'
  ASSOCIATED_MODEL = model.Region

  def Create(self, layer):
    """Creates a new region.

    POST Args:
      Expects POST arguments with the same names as the model.Region properties.

    Args:
      layer: The layer to which the new region will belong.
    """
    try:
      name = self.request.get('name') or None
      north = float(self.request.get('north'))
      south = float(self.request.get('south'))
      east = float(self.request.get('east'))
      west = float(self.request.get('west'))
      min_altitude = float(self.request.get('min_altitude') or 0) or None
      max_altitude = float(self.request.get('max_altitude') or 0) or None
      altitude_mode = self.request.get('altitude_mode') or None
      lod_min = int(self.request.get('lod_min') or 0) or None
      lod_max = int(self.request.get('lod_max') or 0) or None
      lod_fade_min = int(self.request.get('lod_fade_min') or 0) or None
      lod_fade_max = int(self.request.get('lod_fade_max') or 0) or None

      region = model.Region(layer=layer,
                            name=name,
                            north=north,
                            south=south,
                            east=east,
                            west=west,
                            min_altitude=min_altitude,
                            max_altitude=max_altitude,
                            altitude_mode=altitude_mode,
                            lod_min=lod_min,
                            lod_max=lod_max,
                            lod_fade_min=lod_fade_min,
                            lod_fade_max=lod_fade_max)

      _ValidateRegion(region)

      region.put()
      region.GenerateKML()  # Build cache.
    except (db.BadValueError, TypeError, ValueError), e:
      raise util.BadRequest(str(e))
    else:
      self.response.out.write(region.key().id())

  def Update(self, layer):
    """Updates a region's properties.

    POST Args:
      region_id: The ID of the region to update.
      Expects POST arguments with the same names as the model.Region properties.
      All arguments are optional, and those not supplied are left untouched.

    Args:
      layer: The layer to which the region to update belongs.
    """
    region_id = self.request.get('region_id')
    region = util.GetInstance(model.Region, region_id, layer)
    try:
      for property_name in model.Region.properties():
        value = self.request.get(property_name, None)
        if not value and value is not None:
          setattr(region, property_name, None)
        elif value is not None:
          try:
            if property_name.startswith('lod_'):
              value = int(value)
            elif property_name not in ('altitude_mode', 'name'):
              value = float(value)
          except (TypeError, ValueError):
            raise util.BadRequest('Invalid %s specified.' % property_name)
          setattr(region, property_name, value)
      property_name = None

      _ValidateRegion(region)

      region.ClearCache()
      region.put()
      region.GenerateKML()  # Rebuild cache.
    except db.BadValueError, e:
      if property_name:
        raise util.BadRequest('Invalid %s specified.' % property_name)
      else:
        raise util.BadRequest(str(e))

  def Delete(self, layer):
    """Deletes a region.

    If any entity, link or folder references this region, an error is returned.

    POST Args:
      region_id: The ID of the region to delete.

    Args:
      layer: The layer to which the region to delete belongs.
    """
    region_id = self.request.get('region_id')
    region = util.GetInstance(model.Region, region_id, layer)
    if (region.entity_set.get() or region.folder_set.get() or
        region.link_set.get()):
      raise util.BadRequest('Entities, folders or links referencing this '
                            'region exist.')
    region.delete()


def _ValidateRegion(region):
  if region.south > region.north:
    raise db.BadValueError('North must be higher than South.')
  if region.west > region.east:
    raise db.BadValueError('East must be higher than West.')
  if abs(region.north) > 90:
    raise db.BadValueError('North must be between -90 and 90.')
  if abs(region.south) > 90:
    raise db.BadValueError('South must be between -90 and 90.')
  if (region.lod_min is not None and region.lod_max is not None and
      region.lod_min > region.lod_max):
    raise db.BadValueError('Maximum LOD must be higher than minimum.')
