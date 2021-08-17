import os
import pytest

from mlad.cli import context
from mlad.cli.exceptions import NotExistContextError

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def teardown_function():
    remove_paths = [
        context.ctx_path('test1'),
        context.REF_PATH
    ]
    for path in remove_paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            continue


def test_get():
    with pytest.raises(NotExistContextError):
        context.get('test1')
    mock.add('test1')
    context.use('test1')
    context.get('test1')
    with pytest.raises(NotExistContextError):
        context.get('test2')
