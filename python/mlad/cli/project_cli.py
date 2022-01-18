import getpass
import click
from typing import Optional
from mlad.cli import project
from mlad.cli import train_cli, deploy_cli
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
@click.option('--file', '-f', default=None, help=(
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
@click.option('--file', '-f', default=None, help=(
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


@click.group()
@echo_exception
def train():
    '''Create and manage Train objects.'''
    pass


train.add_command(train_cli.up)
train.add_command(train_cli.down)


@click.group()
@echo_exception
def deploy():
    '''Create and manage Deployment objects.'''
    pass


deploy.add_command(deploy_cli.serve)
deploy.add_command(deploy_cli.update)
deploy.add_command(deploy_cli.kill)
deploy.add_command(deploy_cli.scale)


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
cli.add_command(train)
cli.add_command(deploy)
