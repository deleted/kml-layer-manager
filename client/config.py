"""
config.py sets up connection options and is loaded
by layers.py when the server connection is established.

It's best to put your actual connection options in local_config.py, which is
excluded from version control.  Variable defined there will overwrite the defaults here.
"""
cms_connection_options = (
    'somehost',     #host
    'someuser',     #username
    'somepassword', #password
    False,          #secure
    False,          #save_cookie
)
try:
    from local_config import *
except ImportError:
    pass
