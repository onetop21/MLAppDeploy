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
# mlad project up | mlad up
# mlad project down | mlad down
# mlad prjoect logs | mlad logs
# mlad prjoect scale [service=num]

@click.command()
@click.option('--name', '-n', help='Project name')
@click.option('--version', '-v', default='0.0.1', help='Project version')
@click.option('--maintainer', '-m', default=getpass.getuser(), help='Project maintainer')
def init(name, version, maintainer):
    '''Initialize MLAppDeploy project'''
    project.init(name, version, maintainer)

@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def ls(no_trunc):
    '''Show projects deployed on cluster'''
    project.list(no_trunc)

@click.command()
@click.option('--all', '-a', is_flag=True, help='Show included shutdown service')
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def ps(all, no_trunc):
    '''Show project status deployed on cluster'''
    project.status(all, no_trunc)

@click.command(context_settings={"ignore_unknown_options": True})
@click.option('--build', '-b', is_flag=True, help='Build a project image before run')
@click.argument('arguments', nargs=-1, required=False)
def run(build, arguments):
    '''Deploy and run a project instantly on cluster'''
    project.run(build)

@click.command()
@click.argument('services', nargs=-1, required=False, autocompletion=get_stopped_services_completion)
def up(services):
    '''Deploy and run a project on cluster'''
    project.up(tuple(set(services)))

@click.command()
@click.argument('services', nargs=-1, required=False, autocompletion=get_running_services_completion)
@click.option('--no-dump', is_flag=True, help='Save log to file before down service')
def down(services, no_dump):
    '''Stop and remove current project deployed on cluster'''
    project.down(services, no_dump)

@click.command()
@click.option('--tail', default='all', help='Number of lines to show from the end of logs (default "all")')
@click.option('--timestamps', '-t', is_flag=True, help='Show timestamp with logs')
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.argument('SERVICES|TASKS', nargs=-1, autocompletion=get_running_services_tasks_completion)
def logs(tail, follow, timestamps, **kwargs):
    '''Show current project logs deployed on cluster'''
    filters = kwargs.get('services|tasks')
    project.logs(tail, follow, timestamps, filters)

@click.command()
@click.argument('scales', nargs=-1, autocompletion=get_running_services_completion)
def scale(scales):
    '''Change replicas count of running service in deployed on cluster'''
    project.scale(scales)

@click.command()
def update():
    '''Update Running Project or Service Deployed on Cluster'''

@click.group('project')
@click.option('--file', '-f', default=None, help=f"Specify an alternate project file\t\t\t\n\
        Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable",
        autocompletion=get_project_file_completion)
def cli(file):
    '''Manage machine learning projects'''
    cli_args(file)

def cli_args(file):
    if file != None and not os.path.isfile(file):
        click.echo('Project file is not exist.')
        sys.exit(1)
    file = file or os.environ.get(utils.PROJECT_FILE_ENV_KEY, None)
    if file:
        os.environ[utils.PROJECT_FILE_ENV_KEY] = file

cli.add_command(init)
cli.add_command(ls)
cli.add_command(ps)
cli.add_command(run)
cli.add_command(up)
cli.add_command(down)
cli.add_command(logs)
cli.add_command(scale)
cli.add_command(update)

#sys.modules[__name__] = project
