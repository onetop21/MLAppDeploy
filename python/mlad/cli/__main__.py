import sys
import os
import click
import copy
from mlad import __version__
from mlad.cli import config_cli as config
from mlad.cli import auth_cli as auth
from mlad.cli import image_cli as image
from mlad.cli import project_cli as project
from mlad.cli import plugin_cli as plugin
from mlad.cli import node_cli as node
from mlad.cli.autocompletion import *
from mlad.cli.libs import utils
from mlad.api import API

def has_role(key):
    if utils.has_config():
        config = utils.read_config()
        try:
            token = config.mlad.token[key]
            if token:
                with API(utils.to_url(config.mlad)) as api:
                    res = api.auth.token_verify(token)
                    if res['result']:
                        return res['data']['role'] == key
        except Exception as e:
            #print(f"Exception Handling : {e}", file=sys.stderr)
            return False
    return False

class EntryGroup(click.Group):
    def __init__(self, name=None, commands=None, **attrs):
        click.Group.__init__(self, name, commands, **attrs)
        self._commands = {}
        self._ordered = []
        self._dummy_command = click.Command('')

    def list_commands(self, ctx):
        return self._ordered

    def get_command(self, ctx, name):
        return self._commands.get(name)
        #return self._commands[name] if name in self._commands else self._dummy_command

    def add_command(self, cmd, name, hidden=False):
        self._commands[name] = copy.copy(cmd)
        if hidden: self._commands[name].hidden = True
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
def main(file):
    '''Machine Learning Application Deployment Tool. (https://github.com/onetop21/MLAppDeploy.git)'''
    project.cli_args(file)

main.add_command(config.cli, 'config')
if has_role('admin'):
    main.add_command(auth.cli, 'auth')
    main.add_command(node.cli, 'node')
main.add_command(image.cli, 'image')
if has_role('user'):
    main.add_command(project.cli, 'project')
    main.add_command(plugin.cli, 'plugin')

if has_role('user'):
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

if __name__ == '__main__':
    main()
