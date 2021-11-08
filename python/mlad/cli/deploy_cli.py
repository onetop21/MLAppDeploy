import click
from typing import Optional, List

from mlad.cli import deploy
from mlad.cli.libs import utils

from . import echo_exception


# mlad deploy serve
# mlad deploy kill


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
@click.argument('project-key', required=True)
@click.option('--no-dump', is_flag=True,
              help='Save the log before shutting down the services')
@echo_exception
def kill(project_key: str, no_dump: bool):
    '''Stop and remove the train object on the cluster.'''
    for line in deploy.kill(project_key, no_dump):
        click.echo(line)


@click.command()
@click.argument('project-key', required=True)
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
    for line in deploy.ingress():
        click.echo(line)


@click.group('deploy')
def cli():
    '''Related to the deploy objects'''
    pass


cli.add_command(serve)
cli.add_command(kill)
cli.add_command(scale)
cli.add_command(ingress)
