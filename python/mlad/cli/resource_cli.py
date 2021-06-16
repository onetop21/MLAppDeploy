import click
from mlad.cli import resource


@click.command()
@click.argument('nodes', nargs=-1, required=False)
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def node(nodes, no_trunc):
    '''Show resource status of nodes'''
    resource.list(nodes, no_trunc)


@click.command()
@click.argument('project', nargs=-1, required=False)
def project(projects):
    click.echo('project test')
    click.echo(project)


@click.group('top')
def cli():
    '''Manage resource status of nodes'''


cli.add_command(node)
cli.add_command(project)