import sys
import MLAppDeploy.libs.utils as utils

obj = {
    'username': None,
    'host': '127.0.0.1',
    'endpoint': '127.0.0.1:9000',
    'accesskey': '',
    'secretkey': '',
    'registry': '127.0.0.1:5000'
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
