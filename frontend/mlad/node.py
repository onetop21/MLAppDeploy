import sys, os, click
import MLAppDeploy as mlad

# mlad node ls
# mlad node enable [name]
# mlad node disable [name]
# //mlad node lable [name] [key=value]

@click.command()
def ls():
    '''Show Connected Nodes.'''
    mlad.node.list()

@click.command()
@click.argument('ID')
def enable(id):
    '''Enable to Use Node.'''
    mlad.node.enable(id)

@click.command()
@click.argument('ID')
def disable(id):
    '''Disable to Use Node.'''
    mlad.node.disable(id)

@click.command()
@click.argument('KV', nargs=-1)
@click.pass_obj
def add(node, kv):
    '''Add label to node.'''
    kvdict = dict([ _.split('=') for _ in kv ])
    mlad.node.label_add(node, **kvdict)

@click.command()
@click.argument('KEY', nargs=-1)
@click.pass_obj
def rm(node, key):
    '''Remove label from node.'''
    mlad.node.label_rm(node, *key)

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
