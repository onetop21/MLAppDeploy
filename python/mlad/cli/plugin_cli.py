import sys
import os
import getpass
import click
from mlad.cli import plugin
from mlad.cli.libs import utils
from mlad.cli.autocompletion import *

# mlad plugin init                                  # 플러그인 스크립트 생성
# mlad plugin install [PATH|GitRepo]                # 플러그인 설치
# mlad plugin installed                             # 설치된 플러그인 목록
# mlad plugin enable                                # 플러그인 환경 활성화 (개인용)
# mlad plugin disable                               # 플러그인 환경 비활성화 (개인용)
# mlad plugin ls                                    # 현재 실행중인 플러그인 목록
# mlad plugin run [NAME] [OPTIONS]                  # 플러그인 실행(FG)
# mlad plugin start [NAME] [OPTIONS]                # 플러그인 실행(BG)
# mlad plugin stop [NAME] [OPTIONS]                 # 플러그인 종료(BG)

@click.command()
@click.option('--name', '-n', help='Plugin Name')
@click.option('--version', '-v', default='0.1', help='Plugin Version')
@click.option('--maintainer', '-m', default=getpass.getuser(), help='Plugin Maintainer')
def init(name, version, maintainer):
    '''Initialize MLAppDeploy Plugin.'''
    plugin.init(name, version, maintainer)

@click.command()
@click.option('--verbose', '-v', is_flag=True, help='Print detail-log during build a plugin.')
@click.option('--no-cache', is_flag=True, help='Do not use the cache when building the plugin.')
def install(verbose, no_cache):
    '''Build and Install MLAppDeploy Plguin.'''
    plugin.install(verbose, no_cache)

@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output.')
def ls(no_trunc):
    '''Show Running Plugins on Cluster.'''
    plugin.list(no_trunc)

@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output.')
def installed(no_trunc):
    '''Show Installed Plugins.'''
    plugin.installed(no_trunc)

@click.command()
@click.argument('name', required=True, autocompletion=get_running_services_completion)
@click.argument('options', nargs=-1, required=False, autocompletion=get_stopped_services_completion)
def run(name, options):
    '''Run Deploy and Run a Project on Local or Cluster.'''
    plugin.run(name, options)

@click.command(context_settings={"ignore_unknown_options": True})
@click.argument('name', required=True, autocompletion=get_running_services_completion)
@click.argument('arguments', nargs=-1, required=False, autocompletion=get_stopped_services_completion)
def start(name, arguments):
    '''Run a Plugin on Background.'''
    plugin.start(name, arguments)

@click.command()
@click.argument('name', nargs=-1, required=True, autocompletion=get_running_services_completion)
def stop(name):
    '''Stop a Running Plugin on Background.'''
    plugin.stop(name)

@click.group('plugin')
def cli():
    '''Manage Machine Learning Projects.'''

cli.add_command(init)
cli.add_command(install)
cli.add_command(installed)
cli.add_command(ls)
#cli.add_command(run)
cli.add_command(start)
cli.add_command(stop)

#sys.modules[__name__] = project
