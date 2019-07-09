import sys
import MLAppDeploy.libs.utils as utils

obj = {
    'account': {
        'username': 'Unknown'
    },
    'docker': {
        'host': '127.0.0.1:2375',
        'registry': '127.0.0.1:5000'
    },
    's3': {
        'endpoint': '127.0.0.1:9000',
        'accesskey': 'MLAPPDEPLOY',
        'secretkey': 'MLAPPDEPLOY'
    }
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
