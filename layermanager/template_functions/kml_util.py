## __BEGIN_LICENSE__
## Copyright (C) 2006-2010 United States Government as represented by
## the Administrator of the National Aeronautics and Space Administration
## All Rights Reserved.
## __END_LICENSE__

from google.appengine.ext.webapp import template
from django import template as django_template
import urlparse

register = template.create_template_register()

@register.simple_tag
def latlon360(latitude, longitude):
    return '%0.2f&#176;%s %0.2f&#176;E' % (abs(latitude), 'NS'[latitude<0], longitude%360)

class BalloonUrlNode(django_template.Node):
    def __init__(self, relative_url):
        self.relative_url = relative_url
    def render(self, context):
        self.base_url = django_template.resolve_variable('base_url', context)
        if self.relative_url == None:
            relative_url = django_template.resolve_variable("relative_url", context)
        else:
            relative_url = self.relative_url
        try:
            base_url = self.base_url.resolve(context)
            return urlparse.urljoin(base_url, relative_url)
        except django_template.VariableDoesNotExist:
            return relative_url

@register.tag
def balloon_url(parser, token):
    try:
        tag_name, relative_url = token.split_contents()
    except ValueError:
        raise django_template.TemplateSyntaxError, "%r tag requires a single argument" % token.contents.split()[0]
    if (relative_url[0] == relative_url[-1] and relative_url[0] in ('"', "'")):
        relative_url = relative_url[1:-1]
    else:
        relative_url = None
    return BalloonUrlNode(relative_url)

