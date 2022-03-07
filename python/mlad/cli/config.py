import sys
import os
import socket
import uuid

import jwt
import yaml

from functools import lru_cache
from typing import Optional, Dict, Callable, List
from pathlib import Path
from urllib.parse import urlparse
from getpass import getuser
from mlad.cli.libs import utils
from mlad.cli.exceptions import (
    ConfigNotFoundError, CannotDeleteConfigError, InvalidPropertyError,
    ConfigAlreadyExistError, InvalidSetPropertyError, InvalidURLError,
    APIServerNotInstalledError
)

MLAD_HOME_PATH = f'{Path.home()}/.mlad'
CFG_PATH = f'{MLAD_HOME_PATH}/config.yml'
CACHE_PATH = f'{MLAD_HOME_PATH}/cache.yml'
StrDict = Dict[str, str]

boilerplate = {
    'current-config': None,
    'configs': []
}

if not os.path.isfile(CFG_PATH):
    Path(MLAD_HOME_PATH).mkdir(exist_ok=True, parents=True)
    with open(CFG_PATH, 'w') as cfg_file:
        yaml.dump(boilerplate, cfg_file)


def _load():
    with open(CFG_PATH, 'r') as cfg_file:
        return yaml.load(cfg_file, Loader=yaml.FullLoader)


def _save(spec: Dict):
    with open(CFG_PATH, 'w') as cfg_file:
        yaml.dump(spec, cfg_file, sort_keys=False)


def _find_config(name: str, spec: Optional[Dict] = None, index: bool = False) -> Optional[Dict]:
    if spec is None:
        spec = _load()

    for i, config in enumerate(spec['configs']):
        if config['name'] == name:
            return config if not index else i

    return None


def add(name: str, admin: bool) -> Dict:
    spec = _load()
    duplicated_index = _find_config(name, spec=spec, index=True)
    if duplicated_index is not None:
        raise ConfigAlreadyExistError(name)

    ip = utils.obtain_my_ip()
    server_config = dict()
    if admin:
        kubeconfig_path = utils.prompt(
            'A Kubeconfig File Path', default=f'{Path.home()}/.kube/config')
        context_name = utils.prompt('A Current Kubernetes Context Name', 'default')
        server_config['kubeconfig_path'] = kubeconfig_path
        server_config['context_name'] = context_name
    else:
        address = utils.prompt('MLAD API Server Address',
                               default=f'http://{ip}:8440')
        address = _parse_url(address)['url']
        server_config = {
            'apiserver': {
                'address': address
            }
        }

    session = _create_session_key()

    warn_insecure = False
    registry_address = utils.prompt('Docker Registry Address', f'http://{ip}:5000')
    parsed_url = _parse_url(registry_address)
    if parsed_url['scheme'] != 'https':
        warn_insecure = True
    registry_address = parsed_url['url']
    registry_namespace = utils.prompt('Docker Registry Namespace')

    base_config = _obtain_dict_from_dotlist([
        f'name={name}',
        f'session={session}',
        f'docker.registry.address={registry_address}',
        f'docker.registry.namespace={registry_namespace}',
        f'admin={admin}'
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

    config = _merge_dict(base_config, server_config, s3_config, db_config)
    if duplicated_index is not None:
        spec['configs'][duplicated_index] = config
    else:
        spec['configs'].append(config)
    if spec['current-config'] is None:
        spec['current-config'] = name

    _save(spec)

    if warn_insecure:
        print('Need to add insecure-registry to docker.json on your all nodes.', file=sys.stderr)
        print('/etc/docker/daemon.json:', file=sys.stderr)
        print(f'  \"insecure-registries\": [\"{registry_address}\"]', file=sys.stderr)

    return config


def use(name: str) -> Dict:
    spec = _load()
    config = _find_config(name, spec=spec)
    if config is None:
        raise ConfigNotFoundError(name)

    spec['current-config'] = name
    _save(spec)
    return config


def _switch(direction: int = 1) -> str:
    spec = _load()
    if spec['current-config'] is None:
        raise ConfigNotFoundError('Any Configs')
    n_configs = len(spec['configs'])
    index = _find_config(spec['current-config'], spec=spec, index=True)
    next_index = (index + direction) % n_configs
    name = spec['configs'][next_index]['name']
    use(name)
    return name


def next() -> str:
    return _switch(direction=1)


def prev() -> str:
    return _switch(direction=-1)


def delete(name: str) -> None:
    spec = _load()
    index = _find_config(name, spec=spec, index=True)
    if index is None:
        raise ConfigNotFoundError(name)
    elif spec['current-config'] == spec['configs'][index]['name']:
        raise CannotDeleteConfigError
    else:
        del spec['configs'][index]
    _save(spec)


@lru_cache(maxsize=None)
def get(name: Optional[str] = None, key: Optional[str] = None) -> Dict:
    if name is None:
        name = current()
    spec = _load()
    config = _find_config(name, spec=spec)
    if config is None:
        raise ConfigNotFoundError(name)
    if key is None:
        return config
    else:
        try:
            keys = key.split('.')
            value = config
            for k in keys:
                value = value[k]
        except KeyError:
            raise InvalidPropertyError(key)
        return value


def set(name: str, *args) -> None:
    spec = _load()
    index = _find_config(name, spec=spec, index=True)
    config = spec['configs'][index]
    try:
        for arg in args:
            keys = arg.split('=')[0].split('.')
            value = config
            for key in keys:
                value = value[key]
            if isinstance(value, dict):
                raise InvalidSetPropertyError(arg)
    except KeyError:
        raise InvalidPropertyError(arg)

    config = _merge_dict(config, _obtain_dict_from_dotlist(args))
    spec['configs'][index] = config
    _save(spec)


def ls():
    spec = _load()
    names = [config['name'] for config in spec['configs']]
    table = [('  NAME',)]
    for name in names:
        table.append([f'  {name}' if spec['current-config'] != name else f'* {name}'])
    utils.print_table(table, 'There are no configs.', 0)


def current():
    spec = _load()
    if spec['current-config'] is None:
        raise ConfigNotFoundError('Any Configs')
    return spec['current-config']


def get_env(dict=False) -> List[str]:
    config = get()
    envs = []

    envs.append(f'MLAD_ADDRESS={obtain_server_address(config)}')
    envs.append(f'MLAD_SESSION={config["session"]}')

    for k, v in config['datastore']['s3'].items():
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

    for k, v in config['datastore']['db'].items():
        if v is None:
            v = ''
        envs.append(f'DB_{k.upper()}={v}')
    envs = sorted(envs)
    return {env.split('=')[0]: env.split('=')[1] for env in envs} if dict else envs


def get_registry_address(config: Dict):
    parsed = _parse_url(config['docker']['registry']['address'])
    registry_address = parsed['address']
    namespace = config['docker']['registry']['namespace']
    if namespace is not None:
        registry_address += f'/{namespace}'
    return registry_address


def is_admin() -> bool:
    return get().get('admin', False)


def obtain_server_address(config: Dict[str, object]) -> str:
    if not config.get('admin', False):
        return config['apiserver']['address']

    from mlad.core.kubernetes import controller as ctlr
    from mlad.core.exceptions import NotFound

    cli = ctlr.get_api_client(config_file=config['kubeconfig_path'], context=config['context_name'])
    host = cli.configuration.host.rsplit(':', 1)[0]
    try:
        ctlr.get_deployment('mlad-api-server', 'mlad', cli=cli)
        service = ctlr.get_service('mlad-api-server', 'mlad', cli=cli)
    except NotFound:
        raise APIServerNotInstalledError
    port = service.spec.ports[0].node_port
    return f'{host}:{port}'


def _create_session_key():
    user = getuser()
    hostname = socket.gethostname()
    payload = {"user": user, "hostname": hostname, "uuid": str(uuid.uuid4())}
    encode = jwt.encode(payload, "mlad", algorithm="HS256")
    return encode


def _parse_url(url):
    try:
        parsed_url = urlparse(url)
        if not parsed_url.netloc:
            raise InvalidURLError
    except Exception:
        raise InvalidURLError
    return {
        'scheme': parsed_url.scheme or 'http',
        'username': parsed_url.username,
        'password': parsed_url.password,
        'hostname': parsed_url.hostname,
        'port': parsed_url.port or (443 if parsed_url.scheme == 'https' else 80),
        'path': parsed_url.path,
        'query': parsed_url.query,
        'params': parsed_url.params,
        'url': url if parsed_url.scheme else f"http://{url}",
        'address': url.replace(f"{parsed_url.scheme}://", "") if parsed_url.scheme else url
    }


def _parse_datastore(kind: str, initializer: Callable[[], StrDict],
                     finalizer: Callable[[StrDict], StrDict], prompts: StrDict) -> Dict:
    config = initializer()
    for k, v in prompts.items():
        config[k] = utils.prompt(v, config[k])
    config = finalizer(config)
    return _obtain_dict_from_dotlist([
        f'datastore.{kind}.{k}={v}' for k, v in config.items()
    ])


def _s3_initializer() -> StrDict:
    ip = utils.obtain_my_ip()
    endpoint = f'http://{ip}:9000'
    region = 'us-east-1'
    access_key = 'minioadmin'
    secret_key = 'minioadmin'
    return {'endpoint': endpoint, 'region': region, 'accesskey': access_key, 'secretkey': secret_key}


def _s3_finalizer(datastore: StrDict) -> StrDict:
    parsed = _parse_url(datastore['endpoint'])
    datastore['endpoint'] = parsed['url']
    datastore['verify'] = parsed['scheme'] == 'https'
    return datastore


def _db_initializer() -> StrDict:
    address = f'mongodb://{utils.obtain_my_ip()}:27017'
    return {'address': address, 'username': '', 'password': ''}


def _db_finalizer(datastore: StrDict) -> StrDict:
    parsed = _parse_url(datastore['address'])
    datastore['address'] = f'mongodb://{parsed["address"]}'
    return datastore


def _obtain_dict_from_dotlist(dotlist):
    ret = dict()
    for elem in dotlist:
        keychain, value = elem.split('=')
        value = yaml.load(value, Loader=yaml.FullLoader)
        keys = keychain.split('.')
        cursor = ret
        for key in keys[:-1]:
            if key not in cursor:
                cursor[key] = dict()
            cursor = cursor[key]
        cursor[keys[-1]] = value
    return ret


def _merge_dict(*dicts):
    ret = dict()
    for elem in dicts:
        for key, value in elem.items():
            if key in ret and isinstance(ret[key], dict) and isinstance(value, dict):
                ret[key] = _merge_dict(ret[key], value)
            else:
                ret[key] = value
    return ret
