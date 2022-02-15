import pytest

from mlad.cli import config
from mlad.cli.exceptions import ConfigNotFoundError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_get():
    with pytest.raises(ConfigNotFoundError):
        config.get('test1')
    mock.add('test1')
    config.use('test1')
    config.get('test1')
    with pytest.raises(ConfigNotFoundError):
        config.get('test2')
