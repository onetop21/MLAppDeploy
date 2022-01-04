import sys
import os
import uuid
from distutils.util import strtobool
from omegaconf import OmegaConf

client_config = {
    'mlad': {
        'address': 'http://localhost:8440',
        'token': {
            'admin': '',
            'user': '',
        },
    },
    'docker': {
        'registry': {
            'address': 'https://docker.io',
            'namespace': ''
        }
    },
    'datastore': {
    }
}

service_config = {
    'docker': {
        'host': 'unix:///var/run/docker.sock',
    },
    'kubernetes': {
        'config': '~/.kube/config'
    },
    'mlad': {
        'orchestrator': 'swarm',
        'debug': False
    },
    'server': {
        'host': os.environ.get('HOST', '0.0.0.0'),
        'port': int(os.environ.get('PORT', 8440)),
        'debug': bool(strtobool(os.environ.get('DEBUG', 'True'))),
    },
    'auth_keys': {
        'admin': str(uuid.uuid4()),
        'user': str(uuid.uuid4()),
    },
}

sys.modules[__name__] = {
    'client': lambda x: OmegaConf.merge(OmegaConf.create(client_config), x),
    'service': lambda x: OmegaConf.merge(OmegaConf.create(service_config), x),
}
