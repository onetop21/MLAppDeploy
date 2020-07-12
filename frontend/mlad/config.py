import sys, os, getpass, click
import MLAppDeploy as mlad

# mlad config init
# mlad config set [key=value]
# mlad config get [key]

@click.command()
@click.option('--username', '-u', default=getpass.getuser(), prompt='Username', help='Set Username.')
@click.option('--address', '-a', default='localhost', prompt='Master IP Address', help='Set Master IP Address.')
def init(username, address):
    '''Initialize Configurations.'''
    mlad.config.init(username, address)

@click.command()
@click.argument('VAR', required=True, nargs=-1)
def set(var):
    '''Set Configurations. [KEY=VALUE]...'''
    mlad.config.set(*var) 

@click.command()
@click.argument('KEY', required=False)
def get(key):
    '''Get Configurations.'''
    mlad.config.get(key)

@click.group()
def cli():
    '''Manage Configuration.'''

cli.add_command(init)
cli.add_command(set)
cli.add_command(get)

#sys.modules[__name__] = config
