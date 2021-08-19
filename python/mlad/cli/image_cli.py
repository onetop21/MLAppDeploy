import sys
import os
import click
from mlad.cli import image
from mlad.cli import project_cli as project
from mlad.cli.autocompletion import *

# mlad image ls
# mlad image search [to be delete]
# mlad image rm
# mlad image prune

####################
# mlad image build {From Project}
# mlad image export [KEY] [FILENAME]
# mlad image import [FILENAME]
# mlad image commit
# -> docker tag, (git commit, git tag) if has .git dir

# mlad image publish [REGISTRY/ORGANIZATION]
# mlad image deploy [...]

@click.command()
@click.option('--all', '-a', is_flag=True, help='Show all project images')
@click.option('--plugin', '-p', is_flag=True, help='Show Plugin images')
@click.option('--tail', '-t', default=10, help='Number of images to show from the latest (default "10")')
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def ls(all, plugin, tail, no_trunc):
    '''Show built image list'''
    image.list(all, plugin, tail, no_trunc)


@click.command()
@click.option('--quiet', '-q', is_flag=True, help='Do not print detail-log during build a project or plugin')
@click.option('--plugin', '-p', is_flag=True, help='Build by plugin manifest')
@click.option('--no-cache', is_flag=True, help='Do not use the cache when building project or plugin')
@click.option('--pull', is_flag=True, help='Attempt to pull the base image even if an older image exists locally.')
def build(quiet, no_cache, pull):
    '''Build MLAppDeploy project or plguin'''
    image.build(quiet, no_cache, pull)


@click.command()
@click.option('--force', '-f', is_flag=True, help='Remove forcely')
@click.argument('ID', nargs=-1, required=True, autocompletion=get_image_list_completion)
def rm(force, id):
    '''Remove built image'''
    image.remove(id, force)

@click.command()
@click.option('--all', '-a', is_flag=True, help='Remove unused all images')
def prune(all):
    '''Remove unused and untagged images'''
    image.prune(all)

@click.group('image')
@click.option('--file', '-f', default=None, help=f"Specify an alternate project file\t\t\t\n\
        Same as {utils.PROJECT_FILE_ENV_KEY} in environment variable",
        autocompletion=get_project_file_completion)
def cli(file):
    '''Manage Docker Image'''
    project.cli_args(file)

cli.add_command(ls)
cli.add_command(build)
cli.add_command(rm)
cli.add_command(prune)

#sys.modules[__name__] = image
