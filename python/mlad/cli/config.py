import os

from typing import Tuple, List, Optional
from pathlib import Path

from mlad.cli import context


def init(address) -> context.Context:
    ctx = context.add('default', address, allow_duplicate=True)
    context.use('default')
    return ctx


def set(*args) -> None:
    return context.set(context.current(), *args)


def get(key: Optional[str] = None) -> str:
    return context.get(context.current(), key)


def env(unset=False) -> Tuple[List[str], str]:
    ctx = get()
    envs = context.get_env(ctx)
    ret = []
    for line in envs:
        if unset:
            K, _ = line.split('=')
            ret.append(f'export {K}=')
        else:
            ret.append(f'export {line}')
    msg = '# To set environment variables, run "eval $(mlad config env)"'
    return ret, msg


def get_env(dict=False):
    ctx = get()
    env = context.get_env(ctx)
    return {e.split('=')[0]: e.split('=')[1] for e in env} if dict else env


def install_completion():
    completion_path = f'{context.MLAD_HOME_PATH}/completion.sh'
    with open(completion_path, 'w') as f:
        f.write(os.popen('_MLAD_COMPLETE=source_bash mlad').read())
    with open(f'{str(Path.home())}/.bash_completion', 'wt') as f:
        f.write(f'. {completion_path}')
