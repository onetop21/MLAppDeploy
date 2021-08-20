import sys
from mlad.core.libs import utils

workspace_default = {
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

dockerfile_default = {
    'apiVersion': 'v1',
    'name': 'Unknown',
    'version': '0.0.1',
    'maintainer': 'Unknown',
    'workdir': './',
    'workspace': {
        'kind': 'Dockerfile',
        'ignores': ['**/.*'],
    },
    'ingress': {},
    'app': {}
}


def update(x):
    kind = x['workspace']['kind']
    return utils.update_obj(workspace_default if kind == 'Workspace' else dockerfile_default, x)


sys.modules[__name__] = lambda x: update(x)
