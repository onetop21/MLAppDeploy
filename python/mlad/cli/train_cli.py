import click
from typing import Optional, List

from mlad.cli import train
from mlad.cli.libs import utils, MutuallyExclusiveOption
from mlad.cli.libs.auth import auth_admin
from mlad.cli.autocompletion import list_project_key

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
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'],
              autocompletion=list_project_key)
@click.option('--no-dump', is_flag=True,
              help='Save the log before shutting down the apps')
@echo_exception
def down(file: Optional[str], project_key: Optional[str], no_dump: bool):
    '''Stop and remove the train object on the cluster.'''
    lines = train.down_force(file, project_key, no_dump) if auth_admin() \
        else train.down(file, project_key, no_dump)
    for line in lines:
        click.echo(line)


@click.command()
@click.argument('scales', required=True, nargs=-1)
@click.option('--file', '-f', default=None, help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'],
              autocompletion=list_project_key)
@echo_exception
def scale(scales: List[str], file: Optional[str], project_key: Optional[str]):
    '''Change the scale of one of the running apps.
    Format: mlad train scale [APP_NAME1]=[SCALE1] [APP_NAME2]=[SCALE2]
    '''
    parsed_scales = []
    for scale in scales:
        app_name, value = scale.split('=')
        value = int(value)
        parsed_scales.append((app_name, value))
    for line in train.scale(parsed_scales, file, project_key):
        click.echo(line)


@click.group('train')
def cli():
    '''Related to the train objects'''
    pass


cli.add_command(up)
cli.add_command(down)
cli.add_command(scale)
