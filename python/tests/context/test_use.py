import pytest

from mlad.cli import context
from mlad.cli.exceptions import NotExistContextError

from . import mock

origin_stdin = None


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_use():
    mock.add('use')
    context.use('use')
    config = context._load()
    assert config.current == 'use'


def test_invalid_use():
    with pytest.raises(NotExistContextError):
        context.use('invalid-use')
