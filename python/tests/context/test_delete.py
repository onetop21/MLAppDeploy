import os
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
    context.use('test1')
    context.delete('test2')

    assert not os.path.isfile(context.ctx_path('test2'))
    with pytest.raises(CannotDeleteContextError):
        context.delete('test1')

    with pytest.raises(NotExistContextError):
        context.delete('test3')
