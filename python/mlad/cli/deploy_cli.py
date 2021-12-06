import click
from typing import Optional, List

from mlad.cli import deploy
from mlad.cli.libs import utils
from mlad.cli.libs.auth import auth_admin
from mlad.cli.autocompletion import list_project_keys

from . import echo_exception


@click.command()
@click.option('--file', '-f', default=None, help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable')
)
@echo_exception
def serve(file: Optional[str]):
    '''Deploy and run a deploy object on the cluster.'''
    for line in deploy.serve(file):
        click.echo(line)


@click.command()
@click.argument('project-key', required=True, autocompletion=list_project_keys)
@click.option('--file', '-f', default=None, help=(
    'Specify an project file to be used for update.\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable')
)
@echo_exception
def update(project_key: str, file: Optional[str]):
    '''Update deployed service with updated project file.\n
    Valid options for update : [image, command, args, scale, env, quota]'''

    for line in deploy.update(project_key, file):
        click.echo(line)


@click.command()
@click.argument('project-key', required=True, autocompletion=list_project_keys)
@click.option('--no-dump', is_flag=True,
              help='Don\'t save the log before shutting down the services')
@echo_exception
def kill(project_key: str, no_dump: bool):
    '''Stop and remove the train object on the cluster.'''
    lines = deploy.kill_force(project_key, no_dump) if auth_admin() \
        else deploy.kill(project_key, no_dump)
    for line in lines:
        click.echo(line)


@click.command()
@click.argument('project-key', required=True, autocompletion=list_project_keys)
@click.argument('scales', required=True, nargs=-1)
@echo_exception
def scale(project_key: str, scales: List[str]):
    '''Change the scale of one of the running apps.
    Format: mlad deploy scale [PROJECT_KEY] [APP_NAME1]=[SCALE1] [APP_NAME2]=[SCALE2]
    '''
    parsed_scales = []
    for scale in scales:
        app_name, value = scale.split('=')
        value = int(value)
        parsed_scales.append((app_name, value))
    for line in deploy.scale(parsed_scales, project_key):
        click.echo(line)


@click.command()
@echo_exception
def ingress():
    '''Show the ingress information of running services.'''
    deploy.ingress()
