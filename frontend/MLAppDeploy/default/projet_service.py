import sys, copy
import MLAppDeploy.utils as utils

obj = {
    'image': '',
    'env': {},
    'depends': [],
    'arguments': '',
    'deploy': {
        'quotes': {
            'cpus': 1,
            'mems': '8G',
            'gpus': 0,
        },
        'constraints': [],
        'replicas': 1,
    }
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
