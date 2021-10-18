import click

from mlad.cli import board
from . import echo_exception


@click.command()
@echo_exception
def activate():
    """Activate MLAD board."""
    click.echo('Start running MLAD board.')
    board.activate()
    click.echo('Successfully activate MLAD board.')


@click.command()
@echo_exception
def deactivate():
    """Deactivate MLAD board and remove components."""
    click.echo('Start deactivating MLAD board.')
    board.deactivate()
    click.echo('Successfully deactivate MLAD board.')


@click.command()
@click.option('--file-path', '-f', required=True, help='The file path of the component')
@click.option('--no-build', is_flag=True, help='Don\'t build the base image')
@echo_exception
def install(file_path: str, no_build: bool):
    """Install a component and attach it to MLAD board."""
    click.echo(f'Read the component spec from {file_path or "./mlad-project.yml"}.')
    board.install(file_path, no_build)
    click.echo('The component installation is complete.')


@click.command()
@click.argument('name', required=True)
@echo_exception
def uninstall(name: str):
    """Uninstall the component and remove it from MLAD board."""
    board.uninstall(name)
    click.echo(f'The component [{name}] is uninstalled')


@click.command()
@echo_exception
def ls():
    """List installed components"""
    board.list()


@click.group('context')
def cli():
    """Manage MLAD board and components."""


cli.add_command(activate)
cli.add_command(deactivate)
cli.add_command(install)
cli.add_command(uninstall)
cli.add_command(ls)
