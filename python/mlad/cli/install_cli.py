import click
from mlad.cli import install
from . import echo_exception


@click.command()
@echo_exception
def check():
    '''Check installed plugins.'''
    for line in install.check():
        click.echo(line)


@click.command('api-server')
@click.argument('IMAGE_TAG', help='An image tag of MLAD api server.')
@click.option('--ingress', is_flag=True, help='Use an ingress to expose the api server.')
@echo_exception
def api_server(image_tag: str, ingress: bool):
    for line in install.api_server(image_tag, ingress):
        click.echo(line)


@click.group('install')
def cli():
    '''Manage installation.'''


cli.add_command(check)
