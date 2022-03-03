import sys
import io
import shutil
import yaml

from mlad.cli import config
from pathlib import Path

origin_stdin = None


def setup():
    config.CFG_PATH = './tests/config.yml'
    Path('./tests').mkdir(exist_ok=True, parents=True)
    with open(config.CFG_PATH, 'w') as cfg_file:
        yaml.dump(config.boilerplate, cfg_file)
    global origin_stdin
    origin_stdin = sys.stdin


def teardown():
    config.CFG_PATH = f'{config.MLAD_HOME_PATH}/config.yml'
    shutil.rmtree('./tests')
    global origin_stdin
    sys.stdin = origin_stdin


def add(name):
    inputs = [
        'https://abc.defg.com',
        'https://abc.defg.com',
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
