import sys
import os
from omegaconf import OmegaConf
from functools import lru_cache
from mlad.core.default import config as default_config

CONFIG_FILE = os.environ.get('MLAD_CONFIG_PATH', '/config.yaml')

@lru_cache(maxsize=None)
def read_config():
    try:
        config = OmegaConf.load(CONFIG_FILE)
    except FileNotFoundError as e:
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
