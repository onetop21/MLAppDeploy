from mlad.cli import context

from . import mock


def setup_function():
    mock.setup()


def teardown_function():
    mock.teardown()


def test_init():
    mock.init()
    config = context._load()
    assert config['current-context'] == 'default'
