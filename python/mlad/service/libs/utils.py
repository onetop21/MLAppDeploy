import sys
import os
from mlad.core.default import config as service_config
from mlad.cli import config as config_core


def is_debug_mode():
    if '-d' in sys.argv or '--debug' in sys.argv or os.environ.get(
            'MLAD_DEBUG', service_config['mlad']['debug']):
        return True
    return False
