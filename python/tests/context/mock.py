import sys
import io
import shutil

from mlad.cli import context
from pathlib import Path

origin_stdin = None


def setup():
    context.DIR_PATH = './tests/contexts'
    context.REF_PATH = './tests/context_ref.yml'
    context.ctx_path = lambda name: f'{context.DIR_PATH}/{name}.yml'
    Path('./tests/contexts').mkdir(exist_ok=True, parents=True)
    global origin_stdin
    origin_stdin = sys.stdin


def teardown():
    context.DIR_PATH = f'{context.MLAD_HOME_PATH}/contexts'
    context.REF_PATH = f'{context.MLAD_HOME_PATH}/context_ref.yml'
    context.ctx_path = lambda name: f'{context.DIR_PATH}/{name}.yml'
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
    return context.add(name, inputs[0])
