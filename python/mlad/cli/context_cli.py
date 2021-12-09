import click

from typing import Optional
from omegaconf import OmegaConf

from mlad.cli import context
from mlad.cli.autocompletion import list_context_names

from . import echo_exception


@click.command()
@click.argument('NAME', required=True)
@click.option('--address', '-a', default='http://localhost:8440',
              prompt='MLAD Service Address', help='MLAD API Server Address.')
@echo_exception
def add(name, address):
    """Add a new context."""
    ret = context.add(name, address)
    click.echo('Context created successfully.')
    click.echo(OmegaConf.to_yaml(ret))


@click.command()
@click.argument('NAME', required=True, autocompletion=list_context_names)
@echo_exception
def use(name: str):
    """Change to the context."""
    context.use(name)
    click.echo(f'Current context name is: [{name}].')


@click.command()
@echo_exception
def next():
    """Change to the next context."""
    name = context.next()
    click.echo(f'Current context name is [{name}].')


@click.command()
@echo_exception
def prev():
    """Change to the previous context."""
    name = context.prev()
    click.echo(f'Current context name is [{name}].')


@click.command()
@click.argument('NAME', required=True)
@echo_exception
def delete(name: str):
    """Delete the context."""
    context.delete(name)
    click.echo(f'Delete the context of [{name}].')


@click.command()
@click.argument('NAME', required=True)
@click.argument('KEY', required=False)
@echo_exception
def get(name: str, key: Optional[str]):
    """Display lower-level information on the context."""
    ret = context.get(name, key)
    try:
        click.echo(OmegaConf.to_yaml(ret)[:-1])
    except ValueError:
        click.echo(ret)


@click.command()
@click.argument('NAME', required=True)
@click.argument('ARGS', required=True, nargs=-1)
@echo_exception
def set(name, args):
    """Set a context entry in config."""
    context.set(name, *args)
    click.echo(f'The context [{name}] is successfully configured.')


@click.command()
@echo_exception
def ls():
    """List contexts."""
    context.ls()


@click.group('context')
def cli():
    """Manage contexts."""


cli.add_command(add)
cli.add_command(use)
cli.add_command(next)
cli.add_command(prev)
cli.add_command(delete)
cli.add_command(get)
cli.add_command(set)
cli.add_command(ls)
