import pytest

from mlad.cli import context
from mlad.cli.exceptions import NotExistContextError

from . import mock

origin_stdin = None


def setup_function():
    mock.setup()


def teardown_function():
    mock.teardown()


def test_next():
    for index in range(5):
        mock.add(f'next-{index}')
    config = context._load()
    assert config.current == 'next-0'
    for index in range(5):
        context.next()
        config = context._load()
        config.current == f'next-{(index + 1) % 5}'


def test_prev():
    for index in range(5):
        mock.add(f'prev-{index}')
    config = context._load()
    assert config.current == 'prev-0'
    for index in range(5):
        context.next()
        config = context._load()
        config.current == f'prev-{(5 - index) % 5}'


def test_invalid_use():
    with pytest.raises(NotExistContextError):
        context.next()
    with pytest.raises(NotExistContextError):
        context.prev()
