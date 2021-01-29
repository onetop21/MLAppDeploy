import sys
import os
import getpass
import click
from datetime import datetime
from datetime import date
from datetime import timedelta
from mlad.cli import auth
from mlad.cli.libs import utils
from mlad.cli.autocompletion import *

# mlad auth create [username] --expired DATE
# mlad auth verify
expired_type = click.DateTime(formats=['%Y-%m-%d', '%Y-%m-%d %H:%M:%S'])
expired_default = date.today() + timedelta(days=7)

@click.command()
@click.option('--expired', '-e', type=expired_type, default=str(expired_default), help='Expired date.')
@click.argument('USERNAME', required=True, nargs=1)
def create(username, expired):
    '''Create User Token.'''
    auth.create(username, expired)

@click.command()
@click.argument('TOKEN', required=False, nargs=1)
def info(token):
    '''Get Information from User Token.'''
    auth.info(token) 

@click.group('auth')
def cli():
    '''Manage Authentication. (Admin Only)'''

cli.add_command(create)
cli.add_command(info)
