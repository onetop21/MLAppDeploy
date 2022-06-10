import click
from mlad.cli import quota
from . import echo_exception


@click.command('set-default')
@click.option('--cpu', required=True, type=float, help='Set default cpu quota limits.')
@click.option('--gpu', required=True, type=int, help='Set default gpu quota limits.')
@click.option('--mem', required=True, help='Set default mem quota limits.')
@echo_exception
def set_default(cpu: float, gpu: int, mem: str):
    '''Set default quota limits for each session.'''
    quota.set_default(cpu, gpu, mem)
    click.echo('Successfully update the quota limits.')


@click.command('set')
@click.argument('SESSION_KEY', required=True)
@click.option('--cpu', required=True, type=float, help='Set cpu quota limits for the session.')
@click.option('--gpu', required=True, type=int, help='Set gpu quota limits for the session.')
@click.option('--mem', required=True, help='Set mem quota limits for the session.')
@echo_exception
def set_quota(session_key: str, cpu: float, gpu: int, mem: str):
    '''Set quota limits for each session.'''
    quota.set_quota(session_key, cpu, gpu, mem)
    click.echo('Successfully update the quota limits.')


@click.group('quota')
def cli():
    '''Manage quota limits.'''


cli.add_command(set_default)
cli.add_command(set_quota)
