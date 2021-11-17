import getpass
import click
from typing import Optional
from mlad.cli import project
from mlad.cli.libs import utils, MutuallyExclusiveOption
from . import echo_exception

# mlad project init
# mlad project ls | mlad ls
# mlad project ps | mlad ps
# mlad prjoect logs | mlad logs


@click.command()
@click.option('--name', '-n', help='Project name')
@click.option('--version', '-v', default='0.0.1', help='Project version')
@click.option('--maintainer', '-m', default=getpass.getuser(), help='Project maintainer')
@echo_exception
def init(name: str, version: str, maintainer: str):
    '''Initialize MLAppDeploy project'''
    project.init(name, version, maintainer)


@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
@echo_exception
def ls(no_trunc: bool):
    '''Show projects deployed on cluster'''
    project.list(no_trunc)


@click.command()
@click.option('--file', '-f', default=None, help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'])
@click.option('--all', '-a', is_flag=True, help='Show included shutdown service')
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
@echo_exception
def ps(file: Optional[str], project_key: Optional[str], all: bool, no_trunc: bool):
    '''Show project status deployed on cluster'''
    project.status(file, project_key, all, no_trunc)


@click.command()
@click.option('--file', '-f', default=None, help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'])
@click.option('--tail', default='all', help='Number of lines to show from the end of logs (default "all")')
@click.option('--timestamps', '-t', is_flag=True, help='Show timestamp with logs')
@click.option('--follow', is_flag=True, help='Follow log output')
@click.argument('SERVICES|TASKS', nargs=-1)
@echo_exception
def logs(file: Optional[str], project_key: Optional[str],
         tail: bool, follow: bool, timestamps: bool, **kwargs):
    '''Show current project logs deployed on cluster'''
    filters = kwargs.get('services|tasks')
    project.logs(file, project_key, tail, follow, timestamps, filters)


@click.group('project')
def cli():
    '''Commands for inspecting and initializing project objects.'''
    pass


cli.add_command(init)
cli.add_command(ls)
cli.add_command(ps)
cli.add_command(logs)
