import pytest

from mlad.cli import context
from mlad.cli.exceptions import ContextNotFoundError

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
    assert config['current-context'] == 'use'


def test_invalid_use():
    with pytest.raises(ContextNotFoundError):
        context.use('invalid-use')
