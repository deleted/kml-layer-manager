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
