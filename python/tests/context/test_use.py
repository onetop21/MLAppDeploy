import sys
import io
import pytest

from omegaconf import OmegaConf
from mlad.cli import context
from mlad.cli.exceptions import NotExistContextError

from . import mock

origin_stdin = None


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_use():
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
    context.add('use', inputs[0])
    context.use('use')
    config = OmegaConf.load(context.REF_PATH)
    assert config.target == context.ctx_path('use')


def test_invalid_use():
    with pytest.raises(NotExistContextError):
        context.use('invalid-use')
