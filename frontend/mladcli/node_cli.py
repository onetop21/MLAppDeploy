import sys, os, click
from mladcli import node

# mlad node ls
# mlad node enable [name]
# mlad node disable [name]
# //mlad node lable [name] [key=value]

@click.command()
def ls():
    '''Show Connected Nodes.'''
    node.list()

@click.command()
@click.argument('ID')
def enable(id):
    '''Enable to Use Node.'''
    node.enable(id)

@click.command()
@click.argument('ID')
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
@click.argument('KEY', nargs=-1)
@click.pass_obj
def rm(id, key):
    '''Remove label from node.'''
    node.label_rm(id, *key)

@click.group()
@click.argument('NODE')
@click.pass_context
def label(context, node):
    '''Manage Docker Image.'''
    context.obj = node

label.add_command(add)
label.add_command(rm)

@click.group()
def cli():
    '''Manage Docker Orchestration Nodes.'''

cli.add_command(ls)
cli.add_command(enable)
cli.add_command(disable)
cli.add_command(label)

#sys.modules[__name__] = node
