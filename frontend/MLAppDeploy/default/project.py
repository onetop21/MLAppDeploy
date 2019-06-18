import sys
import MLAppDeploy.utils as utils

obj = {
    'project': {
        'name': 'Unknown',
        'version': '0.0.0',
        'author': 'Unknown',
    },
    'workspace': {
        'base': 'python:latest',
        'depends': {},
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
