import sys
from mlad.core.libs import utils

obj = {
    'image': '',
    'env': {},
    'depends': [],
    'command': '',
    'arguments': '',
    'deploy': {
        'quotes': {},
        'constraints': {},
        'restart_policy': {
            'condition': 'none',
            'delay': 0,
            'max_attempts': 0,
            'window': 0 
        },
        'replicas': 1,
    }
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
