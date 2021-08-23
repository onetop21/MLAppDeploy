import sys
import os
from mlad.core.default import config as default_config
from mlad.cli import config as config_core

CONFIG_FILE = os.environ.get('MLAD_CONFIG_PATH', '/config.yaml')


def read_config():
    try:
        config = config_core.get()
    except Exception:
        config = {}
    return default_config['service'](config)


def is_debug_mode():
    config = read_config()
    if '-d' in sys.argv or '--debug' in sys.argv or os.environ.get('MLAD_DEBUG', config['mlad']['debug']):
        return True
    return False


def is_kube_mode():
    config = read_config()
    if '-k' in sys.argv or '--kube' in sys.argv or os.environ.get('MLAD_KUBE', config['mlad']['orchestrator'].lower()=='kube'):
        return True
    return False
