import sys
import io
import os

from omegaconf import OmegaConf
from mlad.cli import context

origin_stdin = None
HOME_PATH = context.MLAD_HOME_PATH
DIR_PATH = context.DIR_PATH


def setup_module():
    global origin_stdin
    origin_stdin = sys.stdin


def teardown_module():
    global origin_stdin
    sys.stdin = origin_stdin
    filenames = ['set-default']
    for filename in filenames:
        try:
            os.remove(f'{DIR_PATH}/{filename}.yml')
        except OSError:
            continue


def test_set_default():
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
    context.add('set-default', inputs[0])
    context.set_default('set-default')
    config = OmegaConf.load(f'{HOME_PATH}/target.yml')
    assert config.target == f'{DIR_PATH}/set-default.yml'
