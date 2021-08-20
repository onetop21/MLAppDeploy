import click

from typing import Optional
from omegaconf import OmegaConf

from mlad.cli import context


@click.command()
@click.argument('NAME', required=True)
@click.option('--address', '-a', default='http://localhost:8440',
              prompt='MLAD Service Address', help='MLAD API Server Address.')
def add(name, address):
    """Add a new context."""
    try:
        ret = context.add(name, address)
        click.echo('Context created successfully.')
        click.echo(OmegaConf.to_yaml(ret))
    except Exception as e:
        click.echo(e)


@click.command()
@click.argument('NAME', required=True)
def use(name: str):
    """Change to the context."""
    try:
        context.use(name)
        click.echo(f'Current context name is: [{name}].')
    except Exception as e:
        click.echo(e)


@click.command()
def next():
    """Change to the next context."""
    try:
        name = context.next()
        click.echo(f'Current context name is [{name}].')
    except Exception as e:
        click.echo(e)


@click.command()
def prev():
    """Change to the previous context."""
    try:
        name = context.prev()
        click.echo(f'Current context name is [{name}].')
    except Exception as e:
        click.echo(e)


@click.command()
@click.argument('NAME', required=True)
def delete(name: str):
    """Delete the context."""
    try:
        context.delete(name)
        click.echo(f'Delete the context of [{name}].')
    except Exception as e:
        click.echo(e)


@click.command()
@click.argument('NAME', required=False)
def get(name: Optional[str]):
    """Display lower-level information on the context."""
    try:
        ret = context.get(name)
        click.echo(OmegaConf.to_yaml(ret))
    except Exception as e:
        click.echo(e)


@click.command()
@click.argument('NAME', required=True)
@click.argument('ARGS', required=True, nargs=-1)
def set(name, args):
    """Set a context entry in config."""
    try:
        context.set(name, *args)
        click.echo(f'The context [{name}] is successfully configured.')
    except Exception as e:
        click.echo(e)


@click.command()
def ls():
    """List contexts."""
    try:
        context.ls()
    except Exception as e:
        click.echo(e)


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
