import pytest

from mlad.cli import config
from mlad.cli.exceptions import CannotDeleteConfigError, ConfigNotFoundError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_delete():
    mock.add('test1')
    mock.add('test2')
    mock.add('test3')
    config.use('test1')
    config.delete('test2')

    assert config._find_config('test2') is None
    spec = config._load()
    assert ['test1', 'test3'] == [conf.name for conf in spec.configs]
    with pytest.raises(CannotDeleteConfigError):
        config.delete('test1')

    with pytest.raises(ConfigNotFoundError):
        config.delete('test4')
