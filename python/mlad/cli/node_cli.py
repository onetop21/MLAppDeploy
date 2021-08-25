import sys, os, click
from mlad.cli import node
from mlad.cli.autocompletion import *


@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def ls(no_trunc):
    '''Show connected nodes'''
    node.list(no_trunc)


@click.command()
@click.argument('ID', autocompletion=get_node_list_completion)
def enable(id):
    '''Enable to use node'''
    node.enable(id)


@click.command()
@click.argument('ID', autocompletion=get_node_list_completion)
def disable(id):
    '''Disable to unuse node'''
    node.disable(id)


@click.command()
@click.argument('KV', nargs=-1)
@click.pass_obj
def add(id, kv):
    '''Add label to node'''
    kvdict = dict([ _.split('=') for _ in kv ])
    node.label_add(id, **kvdict)


@click.command()
@click.argument('KEY', nargs=-1, autocompletion=get_node_label_completion)
@click.pass_obj
def rm(id, key):
    '''Remove label from node'''
    node.label_rm(id, *key)


@click.command()
@click.argument('NAMES', nargs=-1, required=False)
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def resource(names, no_trunc):
    '''Show resource status of nodes'''
    node.resource(names=names, no_trunc=no_trunc)


@click.group()
@click.argument('NODE', autocompletion=get_node_list_completion)
@click.pass_context
def label(context, node):
    '''Manage node labels'''
    context.obj = node

label.add_command(add)
label.add_command(rm)


@click.group('node')
def admin_cli():
    '''Manage nodes (Admin Only)'''

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


#sys.modules[__name__] = node
