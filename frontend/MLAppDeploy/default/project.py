import sys
import MLAppDeploy.libs.utils as utils

obj = {
    'project': {
        'name': 'Unknown',
        'version': '0.0.0',
        'author': 'Unknown',
    },
    'workspace': {
        'base': 'python:latest',
        'requires': {},
        'env': {
            'PYTHONUNBUFFERED': 1
        },
        'ignore': [ '**/.*' ],
        'entrypoint': '',
        'arguments': '',
    },
    'services': {}
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x) 
