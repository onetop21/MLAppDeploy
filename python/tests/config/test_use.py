import pytest

from mlad.cli import config
from mlad.cli.exceptions import ConfigNotFoundError

from . import mock

origin_stdin = None


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_use():
    mock.add('use')
    config.use('use')
    spec = config._load()
    assert spec['current-config'] == 'use'


def test_invalid_use():
    with pytest.raises(ConfigNotFoundError):
        config.use('invalid-use')
