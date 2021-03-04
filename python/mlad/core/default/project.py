import sys
from mlad.core.libs import utils

obj = {
    'project': {
        'name': 'Unknown',
        'version': '0.0.0',
        'author': 'Unknown',
        'working_dir': './', 
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
    'services': {}
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 