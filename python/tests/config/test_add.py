import sys
import io
import pytest

from mlad.cli import config
from mlad.cli.exceptions import ConfigAlreadyExistError, InvalidURLError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_valid_input():
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
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs]))
    expected = {
        'name': 'test-valid',
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
    config_dict = config.add('test-valid', False)
    del config_dict['session']
    assert config_dict == expected


def test_valid_input2():
    inputs = [
        '/home/.kube/config',
        'default',
        'https://abc.defg.com',
        '',
        'http://localhost:9000',
        '',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        '',
        ''
    ]
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs]))
    expected = {
        'name': 'test-valid2',
        'kubeconfig_path': inputs[1],
        'context_name': inputs[2],
        'docker': {'registry': {'address': inputs[3], 'namespace': None}},
        'datastore': {
            's3': {
                'endpoint': inputs[5],
                'region': 'us-east-1',
                'accesskey': inputs[7],
                'secretkey': inputs[8],
                'verify': False
            },
            'db': {
                'address': inputs[9],
                'username': None,
                'password': None
            }
        }
    }
    config_dict = config.add('test-valid2', True)
    del config_dict['session']
    assert config_dict == expected


def test_invalid_input():
    inputs = [
        '',
        'https://abc.defg.com',
        '',
        'http://localhost:9000',
        '',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        '',
        ''
    ]
    with pytest.raises(InvalidURLError):
        sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs]))
        config.add('test-invalid', False)


def test_invalid_input2():
    inputs = [
        'https://abc.defg.com',
        'https://abc.defg.com',
        '',
        '/hello',
        '',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        '',
        ''
    ]
    with pytest.raises(InvalidURLError):
        sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs]))
        config.add('test-invalid2', False)


def test_dupilicate():
    mock.add('test')
    with pytest.raises(ConfigAlreadyExistError):
        mock.add('test')
