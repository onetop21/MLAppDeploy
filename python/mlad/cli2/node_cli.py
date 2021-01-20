import sys, os, click
from mlad.cli import node
from mlad.cli.autocompletion import *

# mlad node ls
# mlad node enable [name]
# mlad node disable [name]
# //mlad node lable [name] [key=value]

@click.command()
def ls():
    '''Show Connected Nodes.'''
    node.list()

@click.command()
@click.argument('ID', autocompletion=get_node_list_completion)
def enable(id):
    '''Enable to Use Node.'''
    node.enable(id)

@click.command()
@click.argument('ID', autocompletion=get_node_list_completion)
def disable(id):
    '''Disable to Use Node.'''
    node.disable(id)

@click.command()
@click.argument('KV', nargs=-1)
@click.pass_obj
def add(id, kv):
    '''Add label to node.'''
    kvdict = dict([ _.split('=') for _ in kv ])
    node.label_add(id, **kvdict)

@click.command()
@click.argument('KEY', nargs=-1, autocompletion=get_node_label_completion)
@click.pass_obj
def rm(id, key):
    '''Remove label from node.'''
    node.label_rm(id, *key)

@click.group()
@click.argument('NODE', autocompletion=get_node_list_completion)
@click.pass_context
def label(context, node):
    '''Manage Docker Image.'''
    context.obj = node

label.add_command(add)
label.add_command(rm)

@click.group('node')
def cli():
    '''Manage Docker Orchestration Nodes.'''

cli.add_command(ls)
cli.add_command(enable)
cli.add_command(disable)
cli.add_command(label)

#sys.modules[__name__] = node
