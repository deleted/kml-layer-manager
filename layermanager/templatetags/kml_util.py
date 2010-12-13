from django import template
import urlparse

register = template.Library()

@register.simple_tag
def latlon360(latitude, longitude):
    return '%0.2f&#176;%s %0.2f&#176;E' % (abs(latitude), 'NS'[latitude<0], longitude%360)

class BalloonUrlNode(template.Node):
    def __init__(self, relative_url):
        self.relative_url = relative_url
        self.base_url = template.Variable('base_url')
    def render(self, context):
        if self.relative_url.__class__ == template.Variable:
            relative_url = self.relative_url.resolve(context)
        else:
            relative_url = self.relative_url
        try:
            base_url = self.base_url.resolve(context)
            return urlparse.urljoin(base_url, relative_url)
        except template.VariableDoesNotExist:
            return relative_url

@register.tag
def balloon_url(parser, token):
    try:
        tag_name, relative_url = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError, "%r tag requires a single argument" % token.contents.split()[0]
    if (relative_url[0] == relative_url[-1] and relative_url[0] in ('"', "'")):
        relative_url = relative_url[1:-1]
    else:
        relative_url = template.Variable(relative_url)
    return BalloonUrlNode(relative_url)

