import sys
import os
import getpass
import click
from mlad.cli import project
from mlad.cli.libs import utils
from mlad.cli.autocompletion import *

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
@click.option('--version', '-v', default='0.0.1', help='Project Version')
@click.option('--author', '-a', default=getpass.getuser(), help='Project Author')
def init(name, version, author):
    '''Initialize MLAppDeploy Project.'''
    project.init(name, version, author)

@click.command()
def ls():
    '''Show Projects Deployed on Cluster.'''
    project.list()

@click.command()
@click.option('--all', '-a', is_flag=True, help='Show included shutdown service.')
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output.')
def ps(all, no_trunc):
    '''Show Project Status Deployed on Cluster.'''
    project.status(all, no_trunc)

@click.command()
@click.option('--tagging', '-t', is_flag=True, help='Tag version to latest image.')
@click.option('--verbose', '-v', is_flag=True, help='Print detail-log during build a image.')
@click.option('--no-cache', is_flag=True, help='Do not use the cache when building the image.')
def build(tagging, verbose, no_cache):
    '''Build Project to Image for Deploying on Cluster.'''
    project.build(tagging, verbose, no_cache)

@click.command()
@click.option('--build', '-b', is_flag=True, help='Build Project Image before Deploy and Run Project')
def test(build):
    '''Deploy and Run a Latest Built Project on Local or Cluster.'''
    project.test(build)

@click.command()
@click.argument('services', nargs=-1, required=False, autocompletion=get_stopped_services_completion)
def up(services):
    '''Deploy and Run a Project on Local or Cluster.'''
    project.up(services)

@click.command()
@click.argument('services', nargs=-1, required=False, autocompletion=get_running_services_completion)
def down(services):
    '''Stop and Remove Current Project Deployed on Cluster.'''
    project.down(services)

@click.command()
@click.option('--tail', default='all', help='Number of lines to show from the end of logs (default "all")')
@click.option('--timestamps', '-t', is_flag=True, help='Show timestamp with logs.')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.argument('SERVICES|TASKS', nargs=-1, autocompletion=get_running_services_tasks_completion)
def logs(tail, follow, timestamps, **kwargs):
    '''Show Current Project Logs Deployed on Cluster.'''
    filters = kwargs.get('services|tasks')
    project.logs(tail, follow, timestamps, filters)

@click.command()
@click.argument('scales', nargs=-1, autocompletion=get_running_services_completion)
def scale(scales):
    '''Change Replicas Count of Running Service in Deployed on Cluster.'''
    project.scale(scales)

@click.command()
def update():
    '''Update Running Project or Service Deployed on Cluster.'''

@click.group('project')
@click.option('--file', '-f', default=None, help='Specify an alternate project file')
@click.option('--workdir', default=None, help='Specify an alternate working directory\t\t\t\n(default: the path of the project file)')
def cli(file, workdir):
    '''Manage Machine Learning Projects.'''
    cli_args(file, workdir)

def cli_args(file, workdir):
    if file != None and not os.path.isfile(file):
        click.echo('Project file is not exist.')
        sys.exit(1)
    utils.apply_project_arguments(file, workdir)

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
