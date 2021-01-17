import sys
from mlad.core.libs import utils

obj = {
    'account': {
        'username': 'Unknown'
    },
    'docker': {
        'host': 'unix:///var/run/docker.sock',
        'registry': ''
    },
    's3': {
        'endpoint': '',
        'region': '',
        'accesskey': '',
        'secretkey': '',
        'verify': True, 
    },
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
