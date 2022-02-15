import click
from mlad.cli import image
from mlad.cli.libs import utils
from mlad.cli.autocompletion import list_image_ids

from . import echo_exception


@click.command()
@click.option('--all', '-a', is_flag=True, help='Show all MLAD relevant images.')
@click.option('--tail', '-t', default=10, help='Number of images to show from the latest (default "10").')
@echo_exception
def ls(all, tail):
    '''Show built images.'''
    image.list(all, tail)


@click.command()
@click.option('--file', '-f', default=None, type=click.Path(exists=True), help=(
    'Specify an alternate project file\t\t\t\n'
    f'Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable.')
)
@click.option('--quiet', '-q', is_flag=True, help='Do not print the detail-log while building a project.')
@click.option('--no-cache', is_flag=True, help='Do not use the cache while building a project.')
@click.option('--pull', is_flag=True, help='Attempt to pull the base image even if an older image exists locally.')
@echo_exception
def build(file, quiet, no_cache, pull):
    '''Build a project image.'''
    for line in image.build(file, quiet, no_cache, pull):
        click.echo(line)
    click.echo('Done.')


@click.command()
@click.option('--force', '-f', is_flag=True, help='Remove forcely.')
@click.argument('ID', nargs=-1, required=True, autocompletion=list_image_ids)
@echo_exception
def rm(force, id):
    '''Remove the built image.'''
    click.echo('Remove project image...')
    image.remove(id, force)
    click.echo('Done.')


@click.command()
@click.option('--all', '-a', is_flag=True, help='Remove unused all images.')
@echo_exception
def prune(all):
    '''Remove unused and untagged images.'''
    image.prune(all)


@click.group('image')
def cli():
    '''Manage Docker Image.'''
    pass


cli.add_command(ls)
cli.add_command(build)
cli.add_command(rm)
cli.add_command(prune)
