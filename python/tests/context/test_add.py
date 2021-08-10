import sys
import io
import os
import pytest

from omegaconf import OmegaConf
from mlad.cli import context
from mlad.cli.libs.exceptions import InvalidURLError

origin_stdin = None
DIR_PATH = context.DIR_PATH


def setup_module():
    global origin_stdin
    origin_stdin = sys.stdin


def teardown_module():
    global origin_stdin
    sys.stdin = origin_stdin
    filenames = ['test-valid', 'test-valid2', 'test-invalid']
    for filename in filenames:
        try:
            os.remove(f'{DIR_PATH}/{filename}.yml')
        except OSError:
            continue


def test_valid_input():
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
    expected = {
        'apiserver': {'address': inputs[0]},
        'docker': {'registry': {'address': inputs[1], 'namespace': 'gameai'}},
        'datastore': {
            's3': {
                'endpoint': inputs[3],
                'region': inputs[4],
                'accesskey': inputs[5],
                'secretkey': inputs[6],
                'verify': True
            },
            'db': {
                'address': inputs[7],
                'username': inputs[8],
                'password': inputs[9]
            }
        }
    }
    assert expected == OmegaConf.to_object(context.add('test-valid', inputs[0]))
    assert os.path.isfile(f'{DIR_PATH}/test-valid.yml')


def test_valid_input2():
    inputs = [
        'https://ncml-dev.cloud.ncsoft.com',
        'https://harbor.sailio.ncsoft.com',
        '',
        'http://localhost:9000',
        '',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        '',
        ''
    ]
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
    expected = {
        'apiserver': {'address': inputs[0]},
        'docker': {'registry': {'address': inputs[1], 'namespace': None}},
        'datastore': {
            's3': {
                'endpoint': inputs[3],
                'region': 'us-east-1',
                'accesskey': inputs[5],
                'secretkey': inputs[6],
                'verify': False
            },
            'db': {
                'address': inputs[7],
                'username': None,
                'password': None
            }
        }
    }
    assert expected == OmegaConf.to_object(context.add('test-valid2', inputs[0]))
    assert os.path.isfile(f'{DIR_PATH}/test-valid2.yml')


def test_invalid_input():
    inputs = [
        '',
        'https://harbor.sailio.ncsoft.com',
        '',
        'http://localhost:9000',
        '',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        '',
        ''
    ]
    with pytest.raises(InvalidURLError) as e:
        sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
        context.add('test-invalid', inputs[0])


def test_invalid_input2():
    inputs = [
        'https://ncml-dev.cloud.ncsoft.com',
        'https://harbor.sailio.ncsoft.com',
        '',
        '/hello',
        '',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        '',
        ''
    ]
    with pytest.raises(InvalidURLError) as e:
        sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
        context.add('test-invalid2', inputs[0])