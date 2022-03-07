import pytest

from mlad.cli import config
from mlad.cli.exceptions import InvalidPropertyError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_set():
    mock.add('test1')
    config.set('test1', 'docker.registry.namespace=null')
    config.set('test1',
               'datastore.s3.endpoint=http://localhost:9000',
               'datastore.s3.verify=False')

    datastore_dict = config.get('test1', 'datastore')
    assert datastore_dict == {
        's3': {
            'endpoint': 'http://localhost:9000',
            'region': 'us-west-1',
            'accesskey': 'minioadmin',
            'secretkey': 'minioadmin',
            'verify': False
        },
        'db': {
            'address': 'mongodb://localhost:27017',
            'username': 'dbadmin',
            'password': 'dbadmin'
        }
    }
    docker_dict = config.get('test1', 'docker')
    assert docker_dict == {
        'registry': {
            'address': 'https://abc.defg.com',
            'namespace': None
        }
    }


def test_invalid_set():
    mock.add('test2')
    config.use('test2')
    config.set('test2', 'datastore.db.address=mongodb://8.8.8.8:27017')
    with pytest.raises(InvalidPropertyError):
        config.set('test2', '')
    with pytest.raises(InvalidPropertyError):
        config.set('test2', 'docker.registries=null')
    with pytest.raises(InvalidPropertyError):
        config.set('test2',
                   'datastore.s3.endpoint=http://localhost:9000',
                   'datastore.s3.hello=False')
