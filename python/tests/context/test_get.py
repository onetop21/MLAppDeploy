import pytest

from mlad.cli import context
from mlad.cli.exceptions import NotExistContextError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_get():
    with pytest.raises(NotExistContextError):
        context.get('test1')
    mock.add('test1')
    context.use('test1')
    context.get('test1')
    with pytest.raises(NotExistContextError):
        context.get('test2')
