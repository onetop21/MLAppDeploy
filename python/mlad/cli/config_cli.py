import os
import click
from omegaconf import OmegaConf
from mlad.cli import config
from mlad.cli.libs import utils
from mlad.cli.autocompletion import get_config_key_completion


@click.command()
@click.option('--address', '-a', default='http://localhost:8440',
              prompt='MLAppDeploy Service Address', help='Set service address')
def init(address):
    '''Initialize configurations'''
    try:
        ret = config.init(address)
        click.echo('Config created successfully.')
        click.echo(OmegaConf.to_yaml(ret))
    except Exception as e:
        click.echo(e)


@click.command()
@click.argument('ARGS', required=True, nargs=-1, autocompletion=get_config_key_completion)
def set(args):
    '''Set configurations. [KEY=VALUE]...'''
    try:
        config.set(*args)
        click.echo('The config is successfully configured.')
    except Exception as e:
        click.echo(e)


@click.command()
def get():
    '''Get configurations'''
    try:
        ret = config.get()
        click.echo(OmegaConf.to_yaml(ret))
    except Exception as e:
        click.echo(e)


@click.command()
@click.option('--unset', '-u', is_flag=True)
def env(unset):
    '''To set environment variables, run "eval $(mlad config env)"'''
    try:
        lines, msg = config.env(unset=unset)
        for line in lines:
            click.echo(line)
        click.echo('')
        click.echo(msg)
    except Exception as e:
        click.echo(e)


@click.command()
@click.option('--install', is_flag=True, help='Install shell-completion to shell(Linux Only)')
def completion(install):
    '''Activate auto completion (Linux Only)'''
    shell = os.path.basename(os.environ.get('SHELL'))
    if shell in ['bash', 'zsh']:
        if install:
            utils.write_completion(shell)
            click.echo(f"Register \"source {utils.COMPLETION_FILE}\" to rc file.")
        else:
            completion_script = utils.get_completion(shell)
            click.echo(completion_script)
            click.echo("# To set environment variables, run \"eval \"$(mlad config completion)\"\"")
    else:
        click.echo(f'Cannot support shell [{shell}].\nSupported Shell: bash, zsh')


@click.group('config')
def cli():
    '''Manage configuration'''


cli.add_command(init)
cli.add_command(set)
cli.add_command(get)
cli.add_command(env)
cli.add_command(completion)
