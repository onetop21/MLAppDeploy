import click

from mlad.cli import board


@click.command()
def activate():
    """Activate MLAD board."""
    try:
        click.echo('Start running MLAD board.')
        board.activate()
        click.echo('Successfully activate MLAD board.')
    except Exception as e:
        click.echo(e)


@click.command()
def deactivate():
    """Deactivate MLAD board and remove components."""
    try:
        click.echo('Start deactivating MLAD board.')
        board.deactivate()
        click.echo('Successfully deactivate MLAD board.')
    except Exception as e:
        click.echo(e)


@click.group('context')
def cli():
    """Manage MLAD board and components."""


cli.add_command(activate)
cli.add_command(deactivate)
