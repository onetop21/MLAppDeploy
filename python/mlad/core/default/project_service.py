import sys
from mlad.core.libs import utils

obj = {
    'image': '',
    'env': {},
    'command': '',
    'arguments': '',
    'ports': [],
    'deploy': {
        'quota': {},
        'constraints': {},
        'restart_policy': {
            'condition': None,
            'delay': 0,
            'max_attempts': 0,
            'window': 0 
        },
        'replicas': 1,
    }
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
