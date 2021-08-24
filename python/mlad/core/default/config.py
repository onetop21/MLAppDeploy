import sys
import os
import uuid
from distutils.util import strtobool
from omegaconf import OmegaConf


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
