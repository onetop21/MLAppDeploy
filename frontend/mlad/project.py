import sys, os, click
import MLAppDeploy as mlad

# mlad project init
# mlad project ls | mlad ls
# mlad project ps | mlad ps
# mlad project build | mlad build
# mlad project up | mlad up
# mlad project down | mlad down
# mlad prjoect logs | mlad logs
# mlad prjoect scale [service=num]
@click.command()
@click.option('--name', '-n', help='Project Name')
@click.option('--version', '-v', help='Project Version')
@click.option('--author', '-a', help='Project Author')
def init(name, version, author):
    '''Initialize MLAppDeploy Project.'''
    mlad.project.init(name, version, author)

@click.command()
def ls():
    '''Show Projects Deployed on Cluster.'''
    mlad.project.list()

@click.command()
@click.option('--all', '-a', is_flag=True, help='Show included shutdown service.')
def ps(all):
    '''Show Project Status Deployed on Cluster.'''
    mlad.project.status(all)

@click.command()
@click.option('--tagging', '-t', is_flag=True, help='Tag version to latest image')
def build(tagging):
    '''Build Project to Image for Deploying on Cluster.'''
    mlad.project.build(tagging)

@click.command()
@click.option('--build', '-b', is_flag=True, help='Build Project Image before Deploy and Run Project')
def test(build):
    '''Deploy and Run a Latest Built Project on Local or Cluster.'''
    mlad.project.test(build)

@click.command()
@click.argument('image', required=False)
def up(image):
    '''Deploy and Run a Project on Local or Cluster.'''
    mlad.project.up(image)

@click.command()
def down():
    '''Stop and Remove Current Project Deployed on Cluster.'''
    mlad.project.down()

@click.command()
@click.option('--tail', '-t', default='255', help='Number of lines to show from the end of logs (default "255")')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
def logs(tail, follow):
    '''Show Current Project Logs Deployed on Cluster.'''
    mlad.project.logs(tail, follow)

@click.command()
@click.argument('scales', nargs=-1)
def scale(scales):
    '''Change Replicas Count of Running Service in Deployed on Cluster.'''
    mlad.project.scale(scales)

@click.command()
def update():
    '''Update Running Project or Service Deployed on Cluster.'''

@click.group()
def cli():
    '''Manage Machine Learning Projects.'''

cli.add_command(init)
cli.add_command(ls)
cli.add_command(ps)
cli.add_command(build)
cli.add_command(up)
cli.add_command(down)
cli.add_command(logs)
cli.add_command(scale)
cli.add_command(update)

#sys.modules[__name__] = project
