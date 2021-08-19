import sys
import io

from mlad.cli import context

from . import mock


def setup_function():
    mock.setup()


def teardown_function():
    mock.teardown()


def test_ls():
    origin_stdout = sys.stdout
    mock.add('test1')
    mock.add('test2')
    sys.stdout = buffer = io.StringIO()
    context.ls(False)
    sys.stdout = origin_stdout
    assert buffer.getvalue() == 'NAME   \n* test1\ntest2  \n'


def test_blank_ls():
    origin_stdout = sys.stdout
    origin_stderr = sys.stderr
    sys.stdout = buffer = io.StringIO()
    sys.stderr = buffer2 = io.StringIO()
    context.ls(False)
    assert buffer.getvalue() == 'NAME\n'
    assert buffer2.getvalue() == 'There are no contexts.\n'

    sys.stdout = origin_stdout
    sys.stderr = origin_stderr