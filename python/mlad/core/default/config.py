import os
from distutils.util import strtobool

service_config = {
    'docker': {
        'host': 'unix:///var/run/docker.sock',
    },
    'kubernetes': {
        'config': '~/.kube/config'
    },
    'mlad': {
        'debug': False
    },
    'server': {
        'host': os.environ.get('HOST', '0.0.0.0'),
        'port': int(os.environ.get('PORT', 8440)),
        'debug': bool(strtobool(os.environ.get('DEBUG', 'True'))),
    }
}
