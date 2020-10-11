import sys, os, click
from mladcli import __version__
from mladcli import config_cli as config
from mladcli import image_cli as image
from mladcli import project_cli as project
from mladcli import node_cli as node

@click.group()
@click.version_option(version=__version__, prog_name='MLAppDeploy')
@click.option('--file', '-f', default=None, hidden=True)
@click.option('--workdir', default=None, hidden=True)
def main(file, workdir):
    '''Machine Learning Application Deployment Tool. (https://github.com/onetop21/MLAppDeploy.git)'''
    project.cli_args(file, workdir)

main.add_command(config.cli, 'config')
main.add_command(image.cli, 'image')
main.add_command(project.cli, 'project')
main.add_command(node.cli, 'node')

# Hidden Command
import copy

def addHiddenCommand(clazz, name):
    inst = copy.copy(clazz)
    inst.hidden = True
    main.add_command(inst, name)

addHiddenCommand(image.ls, 'images')
addHiddenCommand(project.build, 'build')
addHiddenCommand(project.test, 'test')
addHiddenCommand(project.up, 'up')
addHiddenCommand(project.down, 'down')
addHiddenCommand(project.logs, 'logs')
addHiddenCommand(project.ls, 'ls')
addHiddenCommand(project.ps, 'ps')
addHiddenCommand(project.scale, 'scale')
