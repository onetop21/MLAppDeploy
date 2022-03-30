import click
import copy

from mlad import __version__
from mlad.cli import config_cli as config
from mlad.cli import install_cli as install
from mlad.cli import image_cli as image
from mlad.cli import project_cli as project
from mlad.cli import node_cli as node
from mlad.cli import board_cli as board
from mlad.cli.exceptions import ConfigNotFoundError
from mlad.cli.config import get as check_config
from mlad.cli.config import is_admin


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

try:
    check_config()
except ConfigNotFoundError:
    pass
else:
    main.add_command(image.cli, 'image')
    main.add_command(project.cli, 'project')
    main.add_command(board.cli, 'board')
    main.add_command(node.admin_cli if is_admin() else node.cli, 'node')
    if is_admin():
        main.add_command(install.check, 'install-check')

    main.add_dummy_command()
    main.add_dummy_command('\b\bPrefer:')

    main.add_command(image.ls, 'images')
    main.add_command(image.build, 'build')
    main.add_command(project.up, 'up')
    main.add_command(project.down, 'down')
    main.add_command(project.run, 'run')
    main.add_command(project.update, 'update')
    main.add_command(project.ingress, 'ingress')
    main.add_command(project.logs, 'logs')
    main.add_command(project.ls, 'ls')
    main.add_command(project.ps, 'ps')
    main.add_command(project.edit, 'edit')
    main.add_command(project.scale, 'scale')


if __name__ == '__main__':
    main()
