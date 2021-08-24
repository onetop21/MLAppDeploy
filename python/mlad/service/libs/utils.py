import sys
import os
from mlad.core.default import config as service_config
from mlad.cli import config as config_core


CONFIG_FILE = os.environ.get('MLAD_CONFIG_PATH', '/config.yaml')


def read_config():
    try:
        config = config_core.get()
    except Exception:
        config = {}
    return config


def is_debug_mode():
    if '-d' in sys.argv or '--debug' in sys.argv or os.environ.get(
            'MLAD_DEBUG', service_config['mlad']['debug']):
        return True
    return False
