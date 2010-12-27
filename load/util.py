
def human_location(lat, lng):
    """ 
    Return a human-readable location as an HTML-escaped string
    e.g. 11.16&#176;N 224.98&#176;E
        &#176; is the degree glyph, HTML escaped
    """
    if lat < 0:
        north_south = 'S'
    else:
        north_south = 'N'
    if lng < 0:
        east_west = 'W'
    else:
        east_west = 'E'
    
    return u"%3.2f&#176;%s %3.2f&#176;%s" % (lat, north_south, lng, east_west)

def human_date(date_object):
    """
    Convert a datetime to a human-friendly date string.
    e.g. February 29, 2008
    """
    return date_object.strftime("%b %d, %Y")
