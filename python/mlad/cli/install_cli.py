import click
from mlad.cli import install
from . import echo_exception


@click.command()
@echo_exception
def version():
    '''Check MLAD version.'''
    for line in install.version():
        click.echo(line)


@click.command()
@echo_exception
def check():
    '''Check installed plugins.'''
    for line in install.check():
        click.echo(line)


@click.group('install')
def cli():
    '''Manage installation.'''


cli.add_command(version)
cli.add_command(check)
