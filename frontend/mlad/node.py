import sys, os, click
import MLAppDeploy as mlad

# mlad node ls
# mlad node enable [name]
# mlad node disable [name]
# //mlad node lable [name] [key=value]

@click.command()
def ls():
    '''Show Connected Nodes.'''
    mlad.nodes()

@click.command()
def enable():
    '''Enable to Use Node.'''

@click.command()
def disable():
    '''Disable to Use Node.'''

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
