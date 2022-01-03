import click
from mlad.cli import node
from . import echo_exception
from mlad.cli.autocompletion import list_node_names


@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output.')
@echo_exception
def ls(no_trunc):
    '''Display connected nodes.'''
    node.list(no_trunc)


@click.command()
@click.argument('node-name', autocompletion=list_node_names)
@echo_exception
def enable(node_name):
    '''Enable to use node.'''
    node.enable(node_name)


@click.command()
@click.argument('node-name', autocompletion=list_node_names)
@echo_exception
def disable(node_name):
    '''Disable to unuse node.'''
    node.disable(node_name)


@click.command()
@click.argument('KV', nargs=-1)
@click.pass_obj
@echo_exception
def add(id, kv):
    '''Add labels to the node.\n
    Format: mlad node label [NODE_NAME] add [KEY1]=[VALUE1] [KEY2]=[VALUE2]
    '''
    kvdict = dict([_.split('=') for _ in kv])
    node.label_add(id, **kvdict)


@click.command()
@click.argument('KEY', nargs=-1)
@click.pass_obj
@echo_exception
def rm(id, key):
    '''Remove labels from the node.\n
    Format: mlad node label [NODE_NAME] rm [KEY1]=[VALUE1] [KEY2]=[VALUE2]
    '''
    node.label_rm(id, *key)


@click.command()
@click.argument('NAMES', nargs=-1, required=False, autocompletion=list_node_names)
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
@echo_exception
def resource(names, no_trunc):
    '''Show resource status of nodes.'''
    node.resource(names=names, no_trunc=no_trunc)


@click.group()
@click.argument('node-name', autocompletion=list_node_names)
@click.pass_context
@echo_exception
def label(context, node_name):
    '''Manage node labels.'''
    context.obj = node_name


label.add_command(add)
label.add_command(rm)


@click.group('node')
def admin_cli():
    '''Manage nodes.'''


admin_cli.add_command(ls)
admin_cli.add_command(resource)
admin_cli.add_command(enable)
admin_cli.add_command(disable)
admin_cli.add_command(label)


@click.group('node')
def cli():
    '''Show connected nodes'''


cli.add_command(ls)
cli.add_command(resource)
