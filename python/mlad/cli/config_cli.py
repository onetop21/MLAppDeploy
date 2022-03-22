from typing import Optional

import click
import yaml

from mlad.cli import config
from mlad.cli.autocompletion import list_config_names
from . import echo_exception


@click.command()
@click.argument('NAME', required=True)
@click.option('--address', required=False, help='Endpoint to connect MLAppDeploy API server.')
@echo_exception
def add(name, address):
    """Add a new config."""
    ret = config.add(name, address)
    click.echo('Config created successfully.')
    click.echo(yaml.dump(ret, sort_keys=False))


@click.command()
@click.argument('NAME', required=True, autocompletion=list_config_names)
@echo_exception
def use(name: str):
    """Switch to the config."""
    config.use(name)
    click.echo(f'Current config name is: [{name}].')


@click.command()
@echo_exception
def next():
    """Change to the next config."""
    name = config.next()
    click.echo(f'Current config name is [{name}].')


@click.command()
@echo_exception
def prev():
    """Change to the previous config."""
    name = config.prev()
    click.echo(f'Current config name is [{name}].')


@click.command()
@click.argument('NAME', required=True, autocompletion=list_config_names)
@echo_exception
def delete(name: str):
    """Delete the config."""
    config.delete(name)
    click.echo(f'Delete the config of [{name}].')


@click.command()
@click.argument('NAME', required=True, autocompletion=list_config_names)
@click.argument('KEY', required=False)
@echo_exception
def get(name: str, key: Optional[str]):
    """Display the detail specification of the config."""
    ret = config.get(name, key)
    try:
        click.echo(yaml.dump(ret, sort_keys=False)[:-1])
    except ValueError:
        click.echo(ret)


@click.command()
@click.argument('NAME', required=True, autocompletion=list_config_names)
@click.argument('ARGS', required=True, nargs=-1)
@echo_exception
def set(name, args):
    """Update values of the config.\n
    Format: mlad config set [NAME] [KEY1=VALUE1] [KEY2=VALUE2]
    """
    config.set(name, *args)
    click.echo(f'The config [{name}] is successfully configured.')


@click.command()
@echo_exception
def ls():
    """List configs."""
    config.ls()


@click.command()
@click.option('--install', '-i', is_flag=True, help='Install the completion using bash-completion.')
@echo_exception
def completion(install: bool):
    '''Activate auto completion (Linux bash shell only).'''
    if install:
        config.install_completion()
    click.echo('Run the following command to activate autocompletion:')
    click.echo('eval "$(_MLAD_COMPLETE=source_bash mlad)"')


@click.group('config')
def cli():
    """Manage configs."""


cli.add_command(add)
cli.add_command(use)
cli.add_command(next)
cli.add_command(prev)
cli.add_command(delete)
cli.add_command(get)
cli.add_command(set)
cli.add_command(ls)
cli.add_command(completion)
