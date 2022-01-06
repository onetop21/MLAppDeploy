import pytest

from mlad.cli import config
from mlad.cli.exceptions import ConfigNotFoundError

from . import mock

origin_stdin = None


def setup_function():
    mock.setup()


def teardown_function():
    mock.teardown()


def test_next():
    for index in range(5):
        mock.add(f'next-{index}')
    spec = config._load()
    assert spec['current-config'] == 'next-0'
    for index in range(5):
        config.next()
        spec = config._load()
        spec['current-config'] == f'next-{(index + 1) % 5}'


def test_prev():
    for index in range(5):
        mock.add(f'prev-{index}')
    spec = config._load()
    assert spec['current-config'] == 'prev-0'
    for index in range(5):
        config.next()
        spec = config._load()
        spec['current-config'] == f'prev-{(5 - index) % 5}'


def test_invalid_use():
    with pytest.raises(ConfigNotFoundError):
        config.next()
    with pytest.raises(ConfigNotFoundError):
        config.prev()
