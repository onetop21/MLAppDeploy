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

#@click.group()
#def label():
#    '''Manage Docker Image.'''

@click.group()
def cli():
    '''Manage Docker Orchestration Nodes.'''

cli.add_command(ls)
cli.add_command(enable)
cli.add_command(disable)
#node.add_command(label)

#sys.modules[__name__] = node
