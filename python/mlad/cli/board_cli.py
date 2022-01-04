import click

from mlad.cli import board
from mlad.cli.autocompletion import list_component_names

from . import echo_exception


@click.command()
@echo_exception
def activate():
    """Activate MLAD board."""
    for line in board.activate():
        click.echo(line)


@click.command()
@echo_exception
def deactivate():
    """Deactivate MLAD board and remove installed components."""
    for line in board.deactivate():
        click.echo(line)


@click.command()
@click.option('--file-path', '-f', required=True, help='The file path of the component.')
@click.option('--no-build', is_flag=True, help='Don\'t build the base image.')
@echo_exception
def install(file_path: str, no_build: bool):
    """Install a component and attach it to MLAD board."""
    for line in board.install(file_path, no_build):
        click.echo(line)


@click.command()
@click.argument('name', required=True, autocompletion=list_component_names)
@echo_exception
def uninstall(name: str):
    """Uninstall the component and remove it from MLAD board."""
    for line in board.uninstall(name):
        click.echo(line)


@click.command()
@echo_exception
def status():
    """Show a status of the MLAD board and list installed components."""
    for line in board.status():
        click.echo(line)


@click.group('context')
def cli():
    """Manage MLAD board and components."""


cli.add_command(activate)
cli.add_command(deactivate)
cli.add_command(install)
cli.add_command(uninstall)
cli.add_command(status)
