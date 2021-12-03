import click
import copy

from mlad import __version__
from mlad.cli import config_cli as config
from mlad.cli import image_cli as image
from mlad.cli import project_cli as project
from mlad.cli import node_cli as node
from mlad.cli import context_cli as context
from mlad.cli import board_cli as board
from mlad.cli import train_cli as train
from mlad.cli import deploy_cli as deploy
from mlad.cli.libs.auth import auth_admin
from mlad.cli.exceptions import ContextNotFoundError
from mlad.cli.context import get as check_context


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

    def add_command(self, cmd, name, hidden=False):
        self._commands[name] = copy.copy(cmd)
        if hidden:
            self._commands[name].hidden = True
        self._commands[name].name = name
        self._ordered.append(name)

    def add_dummy_command(self, comment=''):
        self._commands[comment] = self._dummy_command
        self._ordered.append(comment)


@click.group(cls=EntryGroup)
@click.version_option(version=__version__, prog_name='MLAppDeploy')
def main():
    '''Machine Learning Application Deployment Tool (https://github.com/onetop21/MLAppDeploy)'''
    pass


main.add_command(config.cli, 'config')
if auth_admin():
    main.add_command(context.cli, 'context')

try:
    check_context()
except ContextNotFoundError:
    pass
else:
    main.add_command(image.cli, 'image')
    main.add_command(project.cli, 'project')
    main.add_command(board.cli, 'board')
    main.add_command(node.admin_cli if auth_admin() else node.cli, 'node')

    main.add_dummy_command()
    main.add_dummy_command('\b\bPrefer:')

    main.add_command(image.ls, 'images')
    main.add_command(image.build, 'build')
    # main.add_command(project.run, 'run')
    main.add_command(train.up, 'up')
    main.add_command(train.down, 'down')
    main.add_command(deploy.serve, 'serve')
    main.add_command(deploy.kill, 'kill')
    main.add_command(deploy.update, 'update')
    main.add_command(project.logs, 'logs')
    main.add_command(project.ls, 'ls')
    main.add_command(project.ps, 'ps')
    # main.add_command(project.scale, 'scale')


if __name__ == '__main__':
    main()
