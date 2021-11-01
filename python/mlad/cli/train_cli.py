import os

import click
from typing import Optional

from mlad.cli import train
from mlad.cli.libs import utils

from . import echo_exception


# mlad train up
# mlad train down

@click.command()
@click.option('--file', '-f', default=None, help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable')
)
@echo_exception
def up(file: Optional[str]):
    '''Deploy and run a train object on the cluster.'''
    for line in train.up(file):
        click.echo(line)


@click.command()
@click.option('--file', '-f', default=None, help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable')
)
@click.option('--project-key', '-p', help='Project Key', default=None)
@click.option('--no-dump', is_flag=True,
              help='Save the log before shutting down the services')
@echo_exception
def down(file: Optional[str], project_key: Optional[str], no_dump: bool):
    '''Stop and remove the train object on the cluster.'''
    for line in train.down(file, project_key, no_dump):
        click.echo(line)


@click.group('train')
def cli():
    '''Related to the train objects'''
    pass


cli.add_command(up)
cli.add_command(down)
