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
@click.option('--expired', '-e', type=expired_type, default=str(expired_default), help='Expired date')
@click.argument('USERNAME', required=True, nargs=1)
def create(username, expired):
    '''Create user token'''
    auth.create(username, expired)

@click.command()
@click.argument('TOKEN', required=False, nargs=1)
def login(token):
    '''Login MLAppDeploy service by token'''
    if not token:
        token = click.prompt('User Token', type=str)
    auth.login(token)

@click.command()
def logout():
    '''Logout MLAppDeploy service'''
    auth.logout()

@click.command()
@click.argument('TOKEN', required=False, nargs=1)
def info(token):
    '''Get information from token'''
    auth.info(token) 

@click.command()
def user_info():
    '''Get user information from token'''
    auth.info() 

@click.group('auth')
def admin_cli():
    '''Manage authentication. (Admin Only)'''
admin_cli.add_command(create)
admin_cli.add_command(login)
admin_cli.add_command(logout)
admin_cli.add_command(info)

@click.group('auth')
def user_cli():
    '''Manage authentication'''
user_cli.add_command(login)
user_cli.add_command(logout)
user_cli.add_command(user_info, 'info')

@click.group('auth')
def cli():
    '''Manage authentication'''
cli.add_command(login)

