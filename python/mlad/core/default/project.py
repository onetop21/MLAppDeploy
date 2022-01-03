import sys
from mlad.core.libs import utils

workspace_default = {
    'apiVersion': 'v1',
    'kind': 'Train',
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
        'args': '',
    },
    'app': {}
}

dockerfile_default = {
    'apiVersion': 'v1',
    'kind': 'Train',
    'name': 'Unknown',
    'version': '0.0.1',
    'maintainer': 'Unknown',
    'workdir': './',
    'workspace': {
        'kind': 'Dockerfile',
        'filePath': 'Dockerfile',
        'ignorePath': '.dockerignore',
    },
    'app': {}
}

buildscript_default = {
    'apiVersion': 'v1',
    'kind': 'Train',
    'name': 'Unknown',
    'version': '0.0.1',
    'maintainer': 'Unknown',
    'workdir': './',
    'workspace': {
        'kind': 'Buildscript',
        'buildscript': 'FROM    python:latest',
        'ignores': ['**/.*'],
    },
    'app': {}
}


def update(x):
    kind = x['workspace'].get('kind', 'Workspace')
    return utils.update_obj(workspace_default if kind == 'Workspace' else
                            dockerfile_default if kind == 'Dockerfile' else buildscript_default, x)


sys.modules[__name__] = lambda x: update(x)
