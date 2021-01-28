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
