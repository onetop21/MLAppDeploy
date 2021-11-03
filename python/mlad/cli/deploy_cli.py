import click
from typing import Optional, Dict

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


@click.group('deploy')
def cli():
    '''Related to the deploy objects'''
    pass


cli.add_command(serve)
cli.add_command(kill)