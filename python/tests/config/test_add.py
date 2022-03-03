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
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
    expected = {
        'name': 'test-valid',
        'apiserver': {'address': inputs[0]},
        'kubeconfig_path': None,
        'context_name': None,
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
    config_dict = config.add('test-valid', inputs[0], False)
    del config_dict['session']
    assert config_dict == expected


def test_valid_input2():
    inputs = [
        'https://abc.defg.com',
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
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
    expected = {
        'name': 'test-valid2',
        'apiserver': {'address': inputs[0]},
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
    config_dict = config.add('test-valid2', inputs[0], True)
    del config_dict['session']
    expected == config_dict


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
        sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
        config.add('test-invalid', inputs[0], False)


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
        sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
        config.add('test-invalid2', inputs[0], False)


def test_dupilicate():
    mock.add('test')
    with pytest.raises(ConfigAlreadyExistError):
        mock.add('test')


def test_allow_duplicate():
    mock.add('test-allow-duplicate')
    inputs = [
        'https://abc.defg.com',
        'Y',
        'https://abc.defg.com',
        '',
        'http://localhost:9000',
        'us-west-1',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        '',
        ''
    ]
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
    expected = {
        'name': 'test-allow-duplicate',
        'apiserver': {'address': inputs[0]},
        'kubeconfig_path': None,
        'context_name': None,
        'docker': {'registry': {'address': inputs[2], 'namespace': None}},
        'datastore': {
            's3': {
                'endpoint': inputs[4],
                'region': inputs[5],
                'accesskey': inputs[6],
                'secretkey': inputs[7],
                'verify': False
            },
            'db': {
                'address': inputs[8],
                'username': None,
                'password': None
            }
        }
    }
    config_dict = config.add('test-allow-duplicate', inputs[0], False, allow_duplicate=True)
    del config_dict['session']
    assert expected == config_dict
