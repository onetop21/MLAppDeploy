import sys
import io

from mlad.cli import context

from . import mock


def setup_module():
    mock.setup()


def teardown_module():
    mock.teardown()


def test_ls():
    origin_stdout = sys.stdout
    mock.add('test1')
    mock.add('test2')
    sys.stdout = buffer = io.StringIO()
    context.ls(False)
    assert buffer.getvalue() == 'NAME \ntest2\ntest1\n'
    sys.stdout = origin_stdout
    context.delete('test1')
    context.delete('test2')


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
