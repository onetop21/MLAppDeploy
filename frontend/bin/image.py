import sys, os, click
import MLAppDeploy as mlad

# mlad image ls
# mlad image search
# mlad image rm
# mlad image prune

@click.command()
@click.option('--all', '-a', is_flag=True, help='Show all project images.')
@click.option('--tail', '-t', default=10, help='Number of images to show from the latest (default "10")')
def ls(all, tail):
    '''Show built image list.'''
    mlad.image.list(all, tail)

@click.command()
@click.argument('KEYWORD', required=True)
def search(keyword):
    '''Search image from registry.'''
    mlad.image.search(keyword)

@click.command()
@click.option('--force', '-f', is_flag=True, help='Remove forcely.')
@click.argument('ID', nargs=-1, required=False)
def rm(force, id):
    '''Remove built image.'''
    mlad.image.remove(id, force)

@click.command()
@click.option('--strong', '-s', is_flag=True, help='Remove unused all project images.')
def prune(strong):
    '''Remove unused and untagged project images.'''
    mlad.image.prune(strong)

@click.group()
def cli():
    '''Manage Docker Image.'''

cli.add_command(ls)
cli.add_command(search)
cli.add_command(rm)
cli.add_command(prune)

#sys.modules[__name__] = image
