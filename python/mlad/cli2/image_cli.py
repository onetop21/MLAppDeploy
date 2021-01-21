import sys
import os
import click
from mlad.cli2 import image
from mlad.cli2.autocompletion import *

# mlad image ls
# mlad image search
# mlad image rm
# mlad image prune

@click.command()
@click.option('--all', '-a', is_flag=True, help='Show all project images.')
@click.option('--tail', '-t', default=10, help='Number of images to show from the latest (default "10")')
def ls(all, tail):
    '''Show built image list.'''
    image.list(all, tail)

@click.command()
@click.argument('KEYWORD', required=True)
def search(keyword):
    '''Search image from registry.'''
    image.search(keyword)

@click.command()
@click.option('--force', '-f', is_flag=True, help='Remove forcely.')
@click.argument('ID', nargs=-1, required=True, autocompletion=get_image_list_completion)
def rm(force, id):
    '''Remove built image.'''
    image.remove(id, force)

@click.command()
@click.option('--all', '-a', is_flag=True, help='Remove unused all project images.')
def prune(all):
    '''Remove unused and untagged project images.'''
    image.prune(all)

@click.group('image')
def cli():
    '''Manage Docker Image.'''

cli.add_command(ls)
cli.add_command(search)
cli.add_command(rm)
cli.add_command(prune)

#sys.modules[__name__] = image
