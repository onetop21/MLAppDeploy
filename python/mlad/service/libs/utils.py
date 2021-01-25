import sys
import os
import uuid
from functools import lru_cache
from distutils.util import strtobool
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError as e:
    from yaml import Loader, Dumper

CONFIG_FILE = os.environ.get('MLAD_CONFIG_PATH', '/config.yaml')

@lru_cache(maxsize=None)
def read_config():
    default_config = {
        'docker': {
            'host': 'unix:///var/run/docker.sock',
        },
        'server': {
            'host': os.environ.get('HOST', '0.0.0.0'),
            'port': int(os.environ.get('PORT', 8440)),
            'debug': bool(strtobool(os.environ.get('DEBUG', 'True')))
        },
        'auth_keys': {
            'admin': uuid.uuid4(), 
            'user' : uuid.uuid4(),
        }
    }

    try:
        with open(CONFIG_FILE) as f:
            config = load(f.read(), Loader=Loader)
        return config or default_config
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return default_config