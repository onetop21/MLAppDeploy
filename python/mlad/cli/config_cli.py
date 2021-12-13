from typing import Optional

import click
from omegaconf import OmegaConf
from mlad.cli import config
from mlad.cli.context_cli import _obtain_host
from . import echo_exception


@click.command()
@click.option('--address', '-a', default=f'{_obtain_host()}:8440',
              prompt='MLAD API Server Address', help='Set API server address.')
@echo_exception
def init(address):
    '''Initialize a configuration.'''
    ret = config.init(address)
    click.echo('Config has been successfully registered.')
    click.echo(OmegaConf.to_yaml(ret))


@click.command()
@click.argument('ARGS', required=True, nargs=-1)
@echo_exception
def set(args):
    '''Update values of the context.\n
    Format: mlad config set [KEY1=VALUE1] [KEY2=VALUE2]'''
    config.set(*args)
    click.echo('The config is successfully configured.')


@click.command()
@click.argument('KEY', required=False)
@echo_exception
def get(key: Optional[str]):
    '''Display a detail specification of the configuration.'''
    ret = config.get(key)
    try:
        click.echo(OmegaConf.to_yaml(ret)[:-1])
    except ValueError:
        click.echo(ret)


@click.command()
@click.option('--unset', '-u', is_flag=True, help='Display only names of the environment variables')
@echo_exception
def env(unset):
    '''To set environment variables, run "eval $(mlad config env)."'''
    lines, msg = config.env(unset=unset)
    for line in lines:
        click.echo(line)
    click.echo('')
    click.echo(msg)


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
    '''Manage configuration.'''


cli.add_command(init)
cli.add_command(set)
cli.add_command(get)
cli.add_command(env)
cli.add_command(completion)
