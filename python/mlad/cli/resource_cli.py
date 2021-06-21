import click
from mlad.cli import resource

@click.command()
@click.argument('nodes', nargs=-1, required=False)
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def node(nodes, no_trunc):
    '''Show resource status of nodes'''
    resource.node_list(nodes, no_trunc)

@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def project(no_trunc):
    '''Show resource status of services in current project'''
    resource.service_list(no_trunc)

@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def projects(no_trunc):
    '''Show resource status of all projects'''
    resource.project_list(no_trunc)

@click.group('top')
def cli():
    '''Manage resource status of nodes'''

cli.add_command(node)
cli.add_command(project)
cli.add_command(projects)