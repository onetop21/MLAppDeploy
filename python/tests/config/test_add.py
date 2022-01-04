import sys
import io
import pytest

from omegaconf import OmegaConf
from mlad.cli import config
from mlad.cli.exceptions import ConfigAlreadyExistError, InvalidURLError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


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
    config_dict = OmegaConf.to_object(config.add('test-valid', inputs[0], False))
    del config_dict['session']
    assert config_dict == expected


def test_valid_input2():
    inputs = [
        'https://ncml-dev.cloud.ncsoft.com',
        '/home/.kube/config',
        'default',
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
    config_dict = OmegaConf.to_object(config.add('test-valid2', inputs[0], True))
    del config_dict['session']
    expected == config_dict


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
    with pytest.raises(InvalidURLError):
        sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
        config.add('test-invalid', inputs[0], False)


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
        'https://ncml-dev.cloud.ncsoft.com',
        'Y',
        'https://harbor.sailio.ncsoft.com',
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
    config_dict = OmegaConf.to_object(
        config.add('test-allow-duplicate', inputs[0], False, allow_duplicate=True)
    )
    del config_dict['session']
    assert expected == config_dict
