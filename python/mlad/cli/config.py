from typing import Tuple, List

from mlad.cli import context


def init(address) -> context.Context:
    ctx = context.add('default', address, allow_duplicate=True)
    context.use('default')
    return ctx


def set(*args) -> None:
    return context.set('default', *args)


def get() -> context.Context:
    return context.get('default')


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
