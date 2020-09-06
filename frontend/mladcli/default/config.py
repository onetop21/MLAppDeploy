import sys
from mladcli.libs import utils

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
        'accesskey': '',
        'secretkey': '',
        'verify': True, 
    }
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
