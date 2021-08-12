import pytest

from omegaconf import OmegaConf
from mlad.cli import context
from mlad.cli.exceptions import (
    InvalidPropertyError, NotExistDefaultContextError
)

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_set():
    mock.add('test1')
    context.set('test1', 'docker.registry.namespace=null')
    context.set('test1',
                'datastore.s3.endpoint=http://localhost:9000',
                'datastore.s3.verify=False')

    expected = {
        'apiserver': {'address': 'https://ncml-dev.cloud.ncsoft.com'},
        'docker': {'registry': {
            'address': 'https://harbor.sailio.ncsoft.com',
            'namespace': None
        }},
        'datastore': {
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
    }
    ctx = context.get('test1')
    assert expected == OmegaConf.to_object(ctx)


def test_invalid_set():
    with pytest.raises(NotExistDefaultContextError):
        context.set(None, 'docker.registry.namespace=null')

    mock.add('test2')
    context.use('test2')
    context.set(None, 'datastore.db.address=mongodb://8.8.8.8:27017')
    with pytest.raises(InvalidPropertyError):
        context.set('test2', '')
    with pytest.raises(InvalidPropertyError):
        context.set('test2', 'docker.registries=null')
    with pytest.raises(InvalidPropertyError):
        context.set('test2',
                    'datastore.s3.endpoint=http://localhost:9000',
                    'datastore.s3.hello=False')
