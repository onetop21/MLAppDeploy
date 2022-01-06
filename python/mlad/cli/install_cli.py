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
@click.argument('image-tag', required=True)
@click.option('--ingress', is_flag=True, help='Use an ingress to expose the api server.')
@echo_exception
def api_server(image_tag: str, ingress: bool):
    '''Deploy the MLAD api server.'''
    for line in install.deploy_api_server(image_tag, ingress):
        click.echo(line)


@click.group('install')
def cli():
    '''Manage installation.'''


cli.add_command(check)
cli.add_command(api_server)
