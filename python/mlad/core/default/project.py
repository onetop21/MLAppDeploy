import sys
from mlad.core.libs import utils

obj = {
    'apiVersion': 'v1',
    'name': 'Unknown',
    'version': '0.0.1',
    'maintainer': 'Unknown',
    'workdir': './',
    'workspace': {
        'kind': 'Workspace',
        'base': 'python:latest',
        'preps': [],
        'script': '',
        'env': {
            'PYTHONUNBUFFERED': 1
        },
        'ignores': ['**/.*'],
        'command': '',
        'arguments': '',
    },
    'ingress': {},
    'app': {}
}

sys.modules[__name__] = lambda x: utils.update_obj(obj, x)
