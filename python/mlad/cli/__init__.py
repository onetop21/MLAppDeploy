import click
from functools import wraps


def echo_exception(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as e:
            click.echo(f'{e.__class__.__name__}: {e}')
    return decorated
