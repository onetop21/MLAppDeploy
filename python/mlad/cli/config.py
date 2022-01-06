import sys
import os
import omegaconf

from typing import Optional, Dict, Callable, List
from pathlib import Path
from omegaconf import OmegaConf
from mlad.cli.libs import utils
from mlad.cli.exceptions import (
    ConfigNotFoundError, CannotDeleteConfigError, InvalidPropertyError,
    ConfigAlreadyExistError
)


MLAD_HOME_PATH = f'{Path.home()}/.mlad'
CFG_PATH = f'{MLAD_HOME_PATH}/config.yml'
ConfigSpec = omegaconf.Container
Config = omegaconf.Container
StrDict = Dict[str, str]

boilerplate = {
    'current-config': None,
    'configs': []
}

if not os.path.isfile(CFG_PATH):
    Path(MLAD_HOME_PATH).mkdir(exist_ok=True, parents=True)
    OmegaConf.save(config=boilerplate, f=CFG_PATH)


def _load():
    return OmegaConf.load(CFG_PATH)


def _save(spec: ConfigSpec):
    OmegaConf.save(config=spec, f=CFG_PATH)


def _find_config(name: str, spec: Optional[ConfigSpec] = None, index: bool = False) -> Optional[Config]:
    if spec is None:
        spec = OmegaConf.load(CFG_PATH)

    for i, config in enumerate(spec.configs):
        if config.name == name:
            return config if not index else i

    return None


def add(name: str, address: str, admin: bool, allow_duplicate=False) -> Config:

    spec = _load()
    duplicated_index = _find_config(name, spec=spec, index=True)
    if duplicated_index is not None:
        if not allow_duplicate:
            raise ConfigAlreadyExistError(name)
        elif utils.prompt('Change the existing session key (Y/N)?', 'N') == 'Y':
            session = utils.create_session_key()
        else:
            session = spec.configs[duplicated_index].session
    else:
        session = utils.create_session_key()

    kubeconfig_path = None
    context_name = None
    if admin:
        kubeconfig_path = utils.prompt(
            'A Kubeconfig File Path', default=f'{Path.home()}/.kube/config')
        context_name = utils.prompt('A Current Kubernetes Context Name', None)
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

    kube_config = OmegaConf.create({
        'kubeconfig_path': kubeconfig_path,
        'context_name': context_name
    })

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

    config = OmegaConf.merge(base_config, kube_config, s3_config, db_config)
    if duplicated_index is not None:
        spec.configs[duplicated_index] = config
    else:
        spec.configs.append(config)
    if spec['current-config'] is None:
        spec['current-config'] = name

    _save(spec)

    if warn_insecure:
        print('Need to add insecure-registry to docker.json on your all nodes.', file=sys.stderr)
        print('/etc/docker/daemon.json:', file=sys.stderr)
        print(f'  \"insecure-registries\": [\"{registry_address}\"]', file=sys.stderr)

    return config


def use(name: str) -> Config:
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
    n_configs = len(spec.configs)
    index = _find_config(spec['current-config'], spec=spec, index=True)
    next_index = (index + direction) % n_configs
    name = spec.configs[next_index].name
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
    elif spec['current-config'] == spec.configs[index].name:
        raise CannotDeleteConfigError
    else:
        del spec.configs[index]
    _save(spec)


def get(name: Optional[str] = None, key: Optional[str] = None) -> Config:
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
        except omegaconf.errors.ConfigKeyError:
            raise InvalidPropertyError(key)
        return value


def set(name: str, *args) -> None:
    spec = _load()
    index = _find_config(name, spec=spec, index=True)
    config = spec.configs[index]
    try:
        for arg in args:
            keys = arg.split('=')[0].split('.')
            value = config
            for key in keys:
                value = value[key]
    except Exception:
        raise InvalidPropertyError(arg)

    config = OmegaConf.merge(config, OmegaConf.from_dotlist(args))
    OmegaConf.update(spec, f'configs.{index}', config)
    _save(spec)


def ls():
    spec = _load()
    names = [config.name for config in spec.configs]
    table = [('  NAME',)]
    for name in names:
        table.append([f'  {name}' if spec['current-config'] != name else f'* {name}'])
    utils.print_table(table, 'There are no configs.', 0)


def current():
    spec = _load()
    if spec['current-config'] is None:
        raise ConfigNotFoundError('Any Configs')
    return spec['current-config']


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


def get_env(dict=False) -> List[str]:
    config = get()
    envs = []

    envs.append(f'MLAD_ADDRESS={config.apiserver.address}')
    envs.append(f'MLAD_SESSION={config.session}')

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


def validate_kubeconfig() -> bool:
    config = get()
    kubeconfig_path = config.kubeconfig_path
    context_name = config.context_name
    try:
        kubeconfig = OmegaConf.load(kubeconfig_path)
    except Exception:
        return False
    return 'current-context' in kubeconfig and (context_name == kubeconfig['current-context'])


def get_context() -> str:
    config = get()
    return config.context_name


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
