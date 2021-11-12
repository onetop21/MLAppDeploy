import click
from mlad.cli import image
from mlad.cli.libs import utils

from . import echo_exception


# mlad image ls
# mlad image rm
# mlad image prune

####################
# mlad image build {From Project}


@click.command()
@click.option('--all', '-a', is_flag=True, help='Show all MLAD related images')
@click.option('--tail', '-t', default=10, help='Number of images to show from the latest (default "10")')
@echo_exception
def ls(all, tail):
    '''Show built image list'''
    image.list(all, tail)


@click.command()
@click.option('--file', '-f', default=None, help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable')
)
@click.option('--quiet', '-q', is_flag=True, help='Do not print detail-log during build a project or plugin')
@click.option('--no-cache', is_flag=True, help='Do not use the cache when building project or plugin')
@click.option('--pull', is_flag=True, help='Attempt to pull the base image even if an older image exists locally.')
@echo_exception
def build(file, quiet, no_cache, pull):
    '''Build MLAppDeploy project or plguin'''
    image.build(file, quiet, no_cache, pull)
    click.echo('Done.')


@click.command()
@click.option('--force', '-f', is_flag=True, help='Remove forcely')
@click.argument('ID', nargs=-1, required=True)
@echo_exception
def rm(force, id):
    '''Remove built image'''
    click.echo('Remove project image...')
    image.remove(id, force)
    click.echo('Done.')


@click.command()
@click.option('--all', '-a', is_flag=True, help='Remove unused all images')
@echo_exception
def prune(all):
    '''Remove unused and untagged images'''
    image.prune(all)


@click.group('image')
def cli():
    '''Manage Docker Image'''
    pass


cli.add_command(ls)
cli.add_command(build)
cli.add_command(rm)
cli.add_command(prune)
