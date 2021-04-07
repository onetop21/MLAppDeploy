import sys
import os
import getpass
import click
from mlad.cli import plugin
from mlad.cli.libs import utils
from mlad.cli.autocompletion import *

# mlad plugin init                                  # 플러그인 스크립트 생성
# mlad plugin install                               # 플러그인 설치 (백그라운드)
# mlad plugin uninstall [NAME]                      # 플러그인 삭제
# mlad plugin installed                             # 설치된 플러그인 목록
# mlad plugin resume [NAME]                         # 플러그인 시작
# mlad plugin pause [NAME]                          # 플러그인 멈춤
# mlad plugin run [NAME] [OPTIONS]                  # 플러그인 인스턴스 실행

@click.command()
@click.option('--name', '-n', help='Plugin name')
@click.option('--version', '-v', default='0.1', help='Plugin version')
@click.option('--maintainer', '-m', default=getpass.getuser(), help='Plugin maintainer')
def init(name, version, maintainer):
    '''Initialize MLAppDeploy plugin'''
    plugin.init(name, version, maintainer)

@click.command()
@click.option('--no-trunc', is_flag=True, help='Don\'t truncate output')
def installed(no_trunc):
    '''Show installed plugins'''
    plugin.installed(no_trunc)

@click.command(context_settings={"ignore_unknown_options": True})
@click.argument('name', required=True)#, autocompletion=get_running_services_completion)
@click.argument('options', nargs=-1, required=False)#, autocompletion=get_stopped_services_completion)
def instant(name, options):
    '''Deploy and run a plugin instantly on cluster'''
    #plugin.run(name, options)

@click.command(context_settings={"ignore_unknown_options": True})
@click.argument('name', required=True)#, autocompletion=get_running_services_completion)
@click.argument('arguments', nargs=-1, required=False)#, autocompletion=get_stopped_services_completion)
def install(name, arguments):
    '''Install a plugin to cluster as a service'''
    plugin.install(name, arguments)

@click.command()
def resume(name):
    '''Resume paused plugin on cluster'''
    pass

@click.command()
def pause(name):
    '''Pause running plugin on cluster'''
    pass

@click.command()
@click.argument('name', required=True)#, autocompletion=get_running_services_completion)
def uninstall(name):
    '''Uninstall a plugin from cluster'''
    plugin.uninstall(name)

@click.group('plugin')
def cli():
    '''Manage plugin for helping machine learning projects'''

cli.add_command(init)
cli.add_command(installed)
cli.add_command(instant)
cli.add_command(install)
cli.add_command(uninstall)
cli.add_command(pause)
cli.add_command(resume)

#sys.modules[__name__] = project
