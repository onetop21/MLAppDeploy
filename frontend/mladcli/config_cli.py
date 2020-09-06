import sys, os, getpass, click
from mladcli import config

# mlad config init
# mlad config set [key=value]
# mlad config get [key]

ADDRESS = os.environ.get('DOCKER_HOST', None) or 'unix:///var/run/docker.sock'

@click.command()
@click.option('--username', '-u', default=getpass.getuser(), prompt='Username', help='Set Username.')
@click.option('--address', '-a', default=ADDRESS, prompt='Master IP Address', help='Set Master IP Address.')
def init(username, address):
    '''Initialize Configurations.'''
    config.init(username, address)

@click.command()
@click.argument('VAR', required=True, nargs=-1)
def set(var):
    '''Set Configurations. [KEY=VALUE]...'''
    config.set(*var) 

@click.command()
@click.argument('KEY', required=False)
def get(key):
    '''Get Configurations.'''
    config.get(key)

@click.group()
def cli():
    '''Manage Configuration.'''

cli.add_command(init)
cli.add_command(set)
cli.add_command(get)

#sys.modules[__name__] = config
