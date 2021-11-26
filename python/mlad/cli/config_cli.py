import subprocess

import click
from omegaconf import OmegaConf
from mlad.cli import config
from mlad.cli.autocompletion import get_config_key_completion
from . import echo_exception


@click.command()
@click.option('--address', '-a', default='http://localhost:8440',
              prompt='MLAppDeploy Service Address', help='Set service address')
@echo_exception
def init(address):
    '''Initialize configurations'''
    ret = config.init(address)
    click.echo('Config created successfully.')
    click.echo(OmegaConf.to_yaml(ret))


@click.command()
@click.argument('ARGS', required=True, nargs=-1, autocompletion=get_config_key_completion)
@echo_exception
def set(args):
    '''Set configurations. [KEY=VALUE]...'''
    config.set(*args)
    click.echo('The config is successfully configured.')


@click.command()
@echo_exception
def get():
    '''Get configurations'''
    ret = config.get()
    click.echo(OmegaConf.to_yaml(ret))


@click.command()
@click.option('--unset', '-u', is_flag=True)
@echo_exception
def env(unset):
    '''To set environment variables, run "eval $(mlad config env)"'''
    lines, msg = config.env(unset=unset)
    for line in lines:
        click.echo(line)
    click.echo('')
    click.echo(msg)


@click.command()
@echo_exception
def autocompletion(install):
    '''Activate auto completion (Linux bash shell only)'''
    subprocess.call(['eval', '"$(_MLAD_COMPLETE=source_bash mlad)"'])
    click.echo('Completion is successfully activated.')


@click.group('config')
def cli():
    '''Manage configuration'''


cli.add_command(init)
cli.add_command(set)
cli.add_command(get)
cli.add_command(env)
cli.add_command(autocompletion)
