import sys, copy
import MLAppDeploy.libs.utils as utils

obj = {
    'image': '',
    'env': {},
    'depends': [],
    'command': '',
    'arguments': '',
    'deploy': {
        'quotes': {},
        'constraints': {},
        'replicas': 1,
    }
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
