import sys
import os
import click
import copy
from mladcli import __version__
from mladcli import config_cli as config
from mladcli import image_cli as image
from mladcli import project_cli as project
from mladcli import node_cli as node

from mladcli.autocompletion import *

class EntryGroup(click.Group):
    def __init__(self, name=None, commands=None, **attrs):
        click.Group.__init__(self, name, commands, **attrs)
        self._commands = {}
        self._ordered = []
        self._dummy_command = click.Command('')

    def list_commands(self, ctx):
        return self._ordered

    def get_command(self, ctx, name):
        return self._commands[name] if name in self._commands else self._dummy_command

    def add_command(self, cmd, name):
        self._commands[name] = copy.copy(cmd)
        self._commands[name].name = name
        self._ordered.append(name)

    def add_dummy_command(self, comment=''):
        self._commands[comment] = self._dummy_command
        self._ordered.append(comment)

@click.group(cls=EntryGroup)
@click.version_option(version=__version__, prog_name='MLAppDeploy')
# Below options from project_cli:cli
@click.option('--file', '-f', default=None, hidden=True, autocompletion=get_project_file_completion,
    help='Specify an alternate project file')
@click.option('--workdir', default=None, hidden=True, autocompletion=get_dir_completion,
    help='Specify an alternate working directory\t\t\t\n(default: the path of the project file)')
def main(file, workdir):
    '''Machine Learning Application Deployment Tool. (https://github.com/onetop21/MLAppDeploy.git)'''
    project.cli_args(file, workdir)

main.add_command(node.cli, 'node')
main.add_command(config.cli, 'config')
main.add_command(image.cli, 'image')
main.add_command(project.cli, 'project')

main.add_dummy_command()
main.add_dummy_command('\b\bPrefer:')

main.add_command(image.ls, 'images')
main.add_command(project.build, 'build')
main.add_command(project.test, 'test')
main.add_command(project.up, 'up')
main.add_command(project.down, 'down')
main.add_command(project.logs, 'logs')
main.add_command(project.ls, 'ls')
main.add_command(project.ps, 'ps')
main.add_command(project.scale, 'scale')

# Hidden Command
#import copy

#def addHiddenCommand(clazz, name):
#    inst = copy.copy(clazz)
#    inst.hidden = False
#    main.add_command(inst, name)

#addHiddenCommand(image.ls, 'images')
#addHiddenCommand(project.build, 'build')
#addHiddenCommand(project.test, 'test')
#addHiddenCommand(project.up, 'up')
#addHiddenCommand(project.down, 'down')
#addHiddenCommand(project.logs, 'logs')
#addHiddenCommand(project.ls, 'ls')
#addHiddenCommand(project.ps, 'ps')
#addHiddenCommand(project.scale, 'scale')
