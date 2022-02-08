import getpass
import click
from typing import Optional, List
from mlad.cli import project, config
from mlad.cli.libs import utils, MutuallyExclusiveOption
from mlad.cli.autocompletion import list_project_keys

from . import echo_exception


@click.command()
@click.option('--name', '-n', help='Project name.')
@click.option('--version', '-v', default='0.0.1', help='Project version.')
@click.option('--maintainer', '-m', default=getpass.getuser(), help='Project maintainer.')
@echo_exception
def init(name: str, version: str, maintainer: str):
    '''Initialize a MLAD project file.'''
    project.init(name, version, maintainer)


@click.command()
@click.argument('file', required=False, type=click.Path(exists=True))
@echo_exception
def edit(file: Optional[str]):
    '''Run editor to edit a MLAD project file.'''
    project.edit(file)


@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output.')
@echo_exception
def ls(no_trunc: bool):
    '''Display projects deployed on the cluster.'''
    for line in project.list(no_trunc):
        click.echo(line)


@click.command()
@click.option('--file', '-f', default=None, type=click.Path(exists=True), help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable.'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'],
              autocompletion=list_project_keys)
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output.')
@click.option('--event', '-e', is_flag=True, help='Show warning events of apps.')
@echo_exception
def ps(file: Optional[str], project_key: Optional[str], no_trunc: bool, event: bool):
    '''Display project status deployed on the cluster.'''
    for line in project.status(file, project_key, no_trunc, event):
        click.echo(line)


@click.command()
@click.option('--file', '-f', default=None, type=click.Path(exists=True), help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable.'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'],
              autocompletion=list_project_keys)
@click.option('--tail', default='all', help='Number of lines to show from the end of logs (default "all").')
@click.option('--timestamps', '-t', is_flag=True, help='Show timestamp with logs.')
@click.option('--follow', is_flag=True, help='Follow log output.')
@click.argument('APPS|TASKS', nargs=-1)
@echo_exception
def logs(file: Optional[str], project_key: Optional[str],
         tail: bool, follow: bool, timestamps: bool, **kwargs):
    '''Display the project logs deployed on the cluster.'''
    filters = kwargs.get('apps|tasks')
    project.logs(file, project_key, tail, follow, timestamps, filters)


@click.command()
@echo_exception
def ingress():
    '''Show the ingress information of running services.'''
    for line in project.ingress():
        click.echo(line)


@click.command()
@click.option('--file', '-f', default=None, type=click.Path(exists=True), help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable.')
)
@echo_exception
def up(file: Optional[str]):
    '''Deploy and run a Train object on the cluster.'''
    for line in project.up(file):
        click.echo(line)


@click.command()
@click.option('--file', '-f', default=None, type=click.Path(exists=True), help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable.'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'],
              autocompletion=list_project_keys)
@click.option('--no-dump', is_flag=True,
              help='Don\'t save the log before shutting down the apps.')
@echo_exception
def down(file: Optional[str], project_key: Optional[str], no_dump: bool):
    '''Stop and remove the Train object on the cluster.'''
    lines = project.down_force(file, project_key, no_dump) if config.validate_kubeconfig() \
        else project.down(file, project_key, no_dump)
    for line in lines:
        click.echo(line)


@click.command()
@click.option('--file', '-f', default=None, type=click.Path(exists=True), help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable.'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'],
              autocompletion=list_project_keys)
@echo_exception
def update(file: Optional[str], project_key: Optional[str]):
    '''Update deployed service with updated project file.\n
    Valid options for updates: [image, command, args, scale, env, quota]'''
    for line in project.update(file, project_key):
        click.echo(line)


@click.command()
@click.option('--file', '-f', default=None, type=click.Path(exists=True), help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable.'),
    cls=MutuallyExclusiveOption, mutually_exclusive=['project_key']
)
@click.option('--project-key', '-k', help='Project Key', default=None,
              cls=MutuallyExclusiveOption, mutually_exclusive=['file'],
              autocompletion=list_project_keys)
@click.argument('scales', required=True, nargs=-1)
@echo_exception
def scale(file: Optional[str], project_key: Optional[str], scales: List[str]):
    '''Change the scale of one of the running apps.\n
    Format: mlad deploy scale [APP_NAME1]=[SCALE1] [APP_NAME2]=[SCALE2]
    '''
    parsed_scales = []
    for scale in scales:
        app_name, value = scale.split('=')
        value = int(value)
        parsed_scales.append((app_name, value))
    for line in project.scale(file, project_key, parsed_scales):
        click.echo(line)


@click.group('project')
def cli():
    '''Commands for creating and monitoring project objects.'''
    pass


cli.add_command(init)
cli.add_command(edit)
cli.add_command(ls)
cli.add_command(ps)
cli.add_command(logs)
cli.add_command(ingress)
cli.add_command(up)
cli.add_command(down)
cli.add_command(update)
cli.add_command(scale)
