import sys
import os
import uuid
from distutils.util import strtobool
from omegaconf import OmegaConf

local_config = {
    'account': {
        'username': 'Unknown'
    },
    'docker': {
        'host': 'unix:///var/run/docker.sock',
        'registry': ''
    },
    's3': {
        'endpoint': '',
        'region': '',
        'accesskey': '',
        'secretkey': '',
        'verify': True, 
    },
}

remote_config = {
    'mlad': {
        'host': 'localhost',
        'port': 8440,
        'token': {
            'admin': '',
            'user': '',
        },
    },
    'docker': {
        'registry': '',
    },
    'environment': {
        's3': {
            'endpoint': '',
            'region': '',
            'accesskey': '',
            'secretkey': '',
            'verify': True, 
        },
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
        'debug': True
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
    'local': lambda x: OmegaConf.merge(OmegaConf.create(local_config), x),
    'remote': lambda x: OmegaConf.merge(OmegaConf.create(remote_config), x),
    'service': lambda x: OmegaConf.merge(OmegaConf.create(service_config), x),
}
