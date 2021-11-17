import sys
import os
import omegaconf

from typing import Optional, Dict, Callable, List
from pathlib import Path
from omegaconf import OmegaConf
from mlad.cli.libs import utils
from mlad.cli.exceptions import (
    ContextNotFoundError, CannotDeleteContextError, InvalidPropertyError,
    ContextAlreadyExistError
)


MLAD_HOME_PATH = f'{Path.home()}/.mlad'
CTX_PATH = f'{MLAD_HOME_PATH}/config.yml'
Config = omegaconf.Container
Context = omegaconf.Container
StrDict = Dict[str, str]

boilerplate = {
    'current-context': None,
    'contexts': []
}

if not os.path.isfile(CTX_PATH):
    Path(MLAD_HOME_PATH).mkdir(exist_ok=True, parents=True)
    OmegaConf.save(config=boilerplate, f=CTX_PATH)


def _load():
    return OmegaConf.load(CTX_PATH)


def _save(config: Config):
    OmegaConf.save(config=config, f=CTX_PATH)


def _find_context(name: str, config: Optional[Config] = None, index: bool = False) -> Optional[Context]:
    if config is None:
        config = OmegaConf.load(CTX_PATH)

    for i, context in enumerate(config.contexts):
        if context.name == name:
            return context if not index else i

    return None


def add(name: str, address: str, allow_duplicate=False) -> Context:

    config = _load()
    duplicated_index = _find_context(name, config=config, index=True)
    if duplicated_index is not None:
        if not allow_duplicate:
            raise ContextAlreadyExistError(name)
        elif utils.prompt('Change the existing session key (Y/N)?', 'N') == 'Y':
            session = utils.create_session_key()
        else:
            session = config.contexts[duplicated_index].session
    else:
        session = utils.create_session_key()
    address = utils.parse_url(address)['url']
    registry_address = 'https://docker.io'
    warn_insecure = False
    service_addr = utils.get_advertise_addr()
    registry_port = utils.get_default_service_port('mlad_registry', 5000)
    if registry_port:
        registry_address = f'http://{service_addr}:{registry_port}'
    registry_address = utils.prompt('Docker Registry Address', registry_address)
    parsed_url = utils.parse_url(registry_address)
    if parsed_url['scheme'] != 'https':
        warn_insecure = True
    registry_address = parsed_url['url']
    registry_namespace = utils.prompt('Docker Registry Namespace')

    base_config = OmegaConf.from_dotlist([
        f'name={name}',
        f'session={session}',
        f'apiserver.address={address}',
        f'docker.registry.address={registry_address}',
        f'docker.registry.namespace={registry_namespace}'
    ])

    s3_prompts = {
        'endpoint': 'S3 Compatible Address',
        'region': 'Region',
        'accesskey': 'Access Key ID',
        'secretkey': 'Secret Access Key'
    }
    s3_config = _parse_datastore('s3', _s3_initializer, _s3_finalizer, s3_prompts)

    db_prompts = {
        'address': 'MongoDB Address',
        'username': 'MongoDB Username',
        'password': 'MongoDB Password'
    }
    db_config = _parse_datastore('db', _db_initializer, _db_finalizer, db_prompts)

    context = OmegaConf.merge(base_config, s3_config, db_config)
    if duplicated_index is not None:
        config.contexts[duplicated_index] = context
    else:
        config.contexts.append(context)
    if config['current-context'] is None:
        config['current-context'] = name

    _save(config)

    if warn_insecure:
        print('Need to add insecure-registry to docker.json on your all nodes.', file=sys.stderr)
        print('/etc/docker/daemon.json:', file=sys.stderr)
        print(f'  \"insecure-registries\": [\"{registry_address}\"]', file=sys.stderr)

    return context


def use(name: str) -> Context:
    config = _load()
    context = _find_context(name, config=config)
    if context is None:
        raise ContextNotFoundError(name)

    config['current-context'] = name
    _save(config)
    return context


def _switch(direction: int = 1) -> str:
    config = _load()
    if config['current-context'] is None:
        raise ContextNotFoundError('Any Contexts')
    n_contexts = len(config.contexts)
    index = _find_context(config['current-context'], config=config, index=True)
    next_index = (index + direction) % n_contexts
    name = config.contexts[next_index].name
    use(name)
    return name


def next() -> str:
    return _switch(direction=1)


def prev() -> str:
    return _switch(direction=-1)


def delete(name: str) -> None:
    config = _load()
    index = _find_context(name, config=config, index=True)
    if index is None:
        raise ContextNotFoundError(name)
    elif config['current-context'] == config.contexts[index].name:
        raise CannotDeleteContextError
    else:
        del config.contexts[index]
    _save(config)


def get(name: Optional[str] = None) -> Context:
    config = _load()
    if name is None:
        name = config['current-context']

    context = _find_context(name, config=config)
    if context is None:
        raise ContextNotFoundError(name)
    return context


def set(name: str, *args) -> None:
    config = _load()
    index = _find_context(name, config=config, index=True)
    context = config.contexts[index]
    try:
        for arg in args:
            keys = arg.split('=')[0].split('.')
            value = context
            for key in keys:
                value = value[key]
    except Exception:
        raise InvalidPropertyError(arg)

    context = OmegaConf.merge(context, OmegaConf.from_dotlist(args))
    OmegaConf.update(config, f'contexts.{index}', context)
    _save(config)


def ls():
    config = _load()
    names = [context.name for context in config.contexts]
    table = [('  NAME',)]
    for name in names:
        table.append([f'  {name}' if config['current-context'] != name else f'* {name}'])
    utils.print_table(table, 'There are no contexts.', 0)


def current():
    config = _load()
    if config['current-context'] is None:
        raise ContextNotFoundError('Any Contexts')
    return config['current-context']


def _parse_datastore(kind: str, initializer: Callable[[], StrDict],
                     finalizer: Callable[[StrDict], StrDict], prompts: StrDict) -> omegaconf.Container:
    config = initializer()
    for k, v in prompts.items():
        config[k] = utils.prompt(v, config[k])
    config = finalizer(config)
    return OmegaConf.from_dotlist([
        f'datastore.{kind}.{k}={v}' for k, v in config.items()
    ])


def _s3_initializer() -> StrDict:
    service_addr = utils.get_advertise_addr()
    minio_port = utils.get_default_service_port('mlad_minio', 9000)
    if minio_port:
        endpoint = f'http://{service_addr}:{minio_port}'
        region = 'ap-northeast-2'
        access_key = 'MLAPPDEPLOY'
        secret_key = 'MLAPPDEPLOY'
    else:
        endpoint = 'https://s3.amazonaws.com'
        region = 'us-east-1'
        access_key = None
        secret_key = None
    return {'endpoint': endpoint, 'region': region, 'accesskey': access_key, 'secretkey': secret_key}


def _s3_finalizer(datastore: StrDict) -> StrDict:
    parsed = utils.parse_url(datastore['endpoint'])
    datastore['endpoint'] = parsed['url']
    datastore['verify'] = parsed['scheme'] == 'https'
    return datastore


def get_env(context: Context) -> List[str]:
    envs = []
    for k, v in context['datastore']['s3'].items():
        if v is None:
            v = ''
        if k == 'endpoint':
            envs.append(f'S3_ENDPOINT={v}')
        elif k == 'verify':
            envs.append(f'S3_USE_HTTPS={1 if v else 0}')
            envs.append('S3_VERIFY_SSL=0')
        elif k == 'accesskey':
            envs.append(f'AWS_ACCESS_KEY_ID={v}')
        elif k == 'secretkey':
            envs.append(f'AWS_SECRET_ACCESS_KEY={v}')
        elif k == 'region':
            envs.append(f'AWS_REGION={v}')
        else:
            envs.append(f'S3_{k.upper()}={v}')

    for k, v in context['datastore']['db'].items():
        if v is None:
            v = ''
        envs.append(f'DB_{k.upper()}={v}')
    envs = sorted(envs)
    return envs


def _db_initializer() -> StrDict:
    service_addr = utils.get_advertise_addr()
    mongo_port = utils.get_default_service_port('mlad_mongodb', 27017)
    if mongo_port:
        address = f'mongodb://{service_addr}:{mongo_port}'
    else:
        address = 'mongodb://localhost:27017'
    return {'address': address, 'username': '', 'password': ''}


def _db_finalizer(datastore: StrDict) -> StrDict:
    parsed = utils.parse_url(datastore['address'])
    datastore['address'] = f'mongodb://{parsed["address"]}'
    return datastore
