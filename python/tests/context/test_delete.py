import pytest

from mlad.cli import context
from mlad.cli.exceptions import CannotDeleteContextError, NotExistContextError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_delete():
    mock.add('test1')
    mock.add('test2')
    mock.add('test3')
    context.use('test1')
    context.delete('test2')

    assert context._find_context('test2') is None
    config = context._load()
    assert ['test1', 'test3'] == [context.name for context in config.contexts]
    with pytest.raises(CannotDeleteContextError):
        context.delete('test1')

    with pytest.raises(NotExistContextError):
        context.delete('test4')
