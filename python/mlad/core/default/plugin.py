import sys
from mlad.core.libs import utils

obj = {
    'plugin': {
        'name': 'Unknown',
        'version': '0.0.0',
        'maintainer': 'Unknown',
        'workdir': './', 
    },
    'workspace': {
        'base': 'python:latest',
        'prescripts': [],
        'postscripts': [],
        'requires': {},
        'env': {
            'PYTHONUNBUFFERED': 1
        },
        'ignore': [ '**/.*' ],
        'command': '',
        'arguments': '',
    },
    'service': {
        'image': '',
        'env': {},
        'command': '',
        'arguments': '',
        'ports': [],
        'expose': 80,
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
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
