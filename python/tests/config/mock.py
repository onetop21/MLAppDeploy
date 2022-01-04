import sys
import io
import shutil

from mlad.cli import config
from pathlib import Path
from omegaconf import OmegaConf

origin_stdin = None


def setup():
    config.CFG_PATH = './tests/config.yml'
    Path('./tests').mkdir(exist_ok=True, parents=True)
    OmegaConf.save(config=config.boilerplate, f=config.CFG_PATH)
    global origin_stdin
    origin_stdin = sys.stdin


def teardown():
    config.CFG_PATH = f'{config.MLAD_HOME_PATH}/config.yml'
    shutil.rmtree('./tests')
    global origin_stdin
    sys.stdin = origin_stdin


def add(name):
    inputs = [
        'https://ncml-dev.cloud.ncsoft.com',
        'https://harbor.sailio.ncsoft.com',
        'gameai',
        'https://localhost:9000',
        'us-west-1',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        'dbadmin',
        'dbadmin'
    ]
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
    return config.add(name, inputs[0], False)
