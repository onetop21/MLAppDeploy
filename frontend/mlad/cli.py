import sys, os, click
import mlad as bin
from mlad import __version__

@click.group()
@click.version_option(version=__version__, prog_name='MLAppDeploy')
def main():
    '''Machine Learning Application Deployment Tool. (https://github.com/onetop21/MLAppDeploy.git)'''

main.add_command(bin.config.cli, 'config')
main.add_command(bin.image.cli, 'image')
main.add_command(bin.project.cli, 'project')
main.add_command(bin.node.cli, 'node')

# Hidden Command
import copy

def addHiddenCommand(clazz, name):
    inst = copy.copy(clazz)
    inst.hidden = True
    main.add_command(inst, name)

addHiddenCommand(bin.image.ls, 'images')
addHiddenCommand(bin.project.build, 'build')
addHiddenCommand(bin.project.test, 'test')
addHiddenCommand(bin.project.up, 'up')
addHiddenCommand(bin.project.down, 'down')
addHiddenCommand(bin.project.logs, 'logs')
addHiddenCommand(bin.project.ls, 'ls')
addHiddenCommand(bin.project.ps, 'ps')
addHiddenCommand(bin.project.scale, 'scale')
