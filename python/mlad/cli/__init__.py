import click
import traceback
from functools import wraps
from mlad.core.exceptions import MLADException


def echo_exception(func):
    @wraps(func)
    def decorated(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except MLADException as e:
            click.echo(f'{e.__class__.__name__}: {e}')
        except Exception as e:
            click.echo(traceback.format_exc())
            click.echo(f'{e.__class__.__name__}: {e}')
    return decorated
