import sys
import os
import getpass
import click
from datetime import datetime
from datetime import date
from datetime import timedelta
from mlad.cli2 import auth
from mlad.cli2.libs import utils
from mlad.cli2.autocompletion import *

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
@click.argument('TOKEN', required=True, nargs=1)
def verify(var):
    '''Verify User Token.'''
    auth.verify(var) 

@click.group('auth')
def cli():
    '''Manage Configuration.'''

cli.add_command(create)
cli.add_command(verify)
