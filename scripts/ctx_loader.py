## __BEGIN_LICENSE__
## Copyright (C) 2006-2010 United States Government as represented by
## the Administrator of the National Aeronautics and Space Administration
## All Rights Reserved.
## __END_LICENSE__

from loader_base import Observation, LayerLoader
import sys
sys.path.insert(0, os.path.join(os.path.split(__file__)[0], 'googlenasa_code') # should be a symlink to the googlenasa/code directory
import ctx

class CtxObservation(Observation):
    @property
    def schemafields(self):
        return {
            "credit_string": "CREDIT STRING HERE",
            "thumb_url": self.thumb_url,
            "overlay_url": self.overlay_url,
            "desctiption": self.description,
            "name": self.name,
            "url": self.url,
            "product_id": self.product_id,
            "imagetime": self.imagetime,
            "longitude": self.longitude,
            "latitude": self.latitude,
        }

class CtxLoader(LayerLoader):

    layername = "CTX Footprints"

    def generate_observations(self, cumindex_dir=None, max_observations=None):
        i = 0
        for rdr in ctx.get_rdrs():
            try:
                obs = CtxObservation(rdr)
            except ValueError, TypeError:
                # TODO: Log Me
                continue # skip records with problematic coordinates
            yield obs
            i += 1
            if max_observations > 0 and i >= max_observations:
                break 

    schema = {
        "name": "ctx_schema",
        "fields": (
            {"name": "thumb_url", "type": "string"},
            {"name": "overlay_url", "type": "string"},
            {"name": "desctiption", "type": "string"},
            {"name": "name", "type": "string"},
            {"name": "url", "type": "string"},
            {"name": "product_id", "type": "string"},
            {"name": "imagetime", "type": "date"},
            {"name": "longitude", "type": "float"},
            {"name": "latitude", "type": "float"},
        ),
    }

    template = {
        "name": "ctx_template",
        "text":"""
<table width="360" border="0" cellpadding="0" cellspacing="0">
  <tr height="45"><td><img width="360" height="40" src="{% balloon_url "img/ctx_title.png" %}"></td></tr>
  <tr height="245">{% if thumb_url %}
  <td>{% if overlay_url %}<a href="{% balloon_url overlay_url %}">{% endif %}<img src="{% balloon_url thumb_url %}" width="360" height="240">{% if overlay_url %}</a>{% endif %}</td>
 {% else %}
  <td align="center">[ Browse image not available for this observation. ]</td>
 {% endif %}</tr>
  {% if overlay_url %}<tr><td><center><table><tr><td valign="middle"><a href="{% balloon_url overlay_url %}"><img src="{% balloon_url "img/kml_feed_small.png" %}"></a></td><td valign="middle"><a href="{% balloon_url overlay_url %}">Load this image.</a></td></tr></table></center></td></tr>{% endif %}
  <tr><td>
    {% if description %}<hr/>
    <h2>{{ name }}</h2>
    {{ description|safe }}
    <p><a href="{{ url|safe }}">Learn more...</a></p>
    {% endif %}
    <hr/>
    <p>This image was taken by the <a href="http://www.msss.com/mro/ctx/">Context Camera (CTX)</a> on board NASA's <a href="http://www.nasa.gov/mission_pages/MRO/">Mars Reconnaissance Orbiter (MRO)</a> spacecraft.</p>
    <p>See this image&rsquo;s <a href="http://viewer.mars.asu.edu/planetview/inst/ctx/{{ product_id|safe }}">ASU data page</a>.</p>
    <b>Product ID:</b> {{ product_id }}<br />
    {% if rationale_desc %}<b>Image of:</b> {{ rationale_desc }}<br />{% endif %}
    <b>Location:</b> {% latlon360 latitude longitude %}<br />
    {% if image_time %}<b>Acquired on:</b> {{ image_time|date:"F j, Y" }}<br />{% endif %}
    <hr/>
    <center>{{ credit_string|safe }}</center>
  </td></tr>
</table>
        """
    }
