import sys
import os
import getpass
import click
from mlad.cli import config
from mlad.cli.libs import utils
from mlad.cli.autocompletion import *

# mlad config init
# mlad config set [key=value]
# mlad config get [key]

@click.command()
@click.option('--address', '-a', default='http://localhost:8440', prompt='MLAppDeploy Service Address', help='Set Service Address.')
@click.option('--token', '-t', default='', help='Set Administrator Token.')
def init(address, token):
    '''Initialize Configurations.'''
    config.init(address, token)

@click.command()
@click.argument('VAR', required=True, nargs=-1, autocompletion=get_config_key_completion)
def set(var):
    '''Set Configurations. [KEY=VALUE]...'''
    config.set(*var) 

@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output.')
@click.argument('KEY', required=False, autocompletion=get_config_key_completion)
def get(no_trunc, key):
    '''Get Configurations.'''
    config.get(key, no_trunc)

@click.command()
@click.option('--unset', '-u', is_flag=True)
def env(unset):
    '''To set environment variables, run "eval $(mlad config env)"'''
    config.env(unset)

@click.command()
@click.option('--install', is_flag=True, help='Install Shell-Completion to Shell(Linux Only).')
def completion(install):
    '''Activate Auto Completion (Linux Only)'''
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
    '''Manage Configuration.'''

cli.add_command(init)
cli.add_command(set)
cli.add_command(get)
cli.add_command(env)
cli.add_command(completion)

#sys.modules[__name__] = config
