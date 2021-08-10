import sys

from pathlib import Path
from omegaconf import OmegaConf
from mlad.cli.libs import utils


MLAD_HOME_PATH = f'{Path.home()}/.mlad'
DIR_PATH = f'{MLAD_HOME_PATH}/contexts'
Path(DIR_PATH).mkdir(exist_ok=True, parents=True)


def add(name, address):

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

    config = OmegaConf.merge(base_config, s3_config, db_config)
    OmegaConf.save(config=config, f=f'{DIR_PATH}/{name}.yml')

    if warn_insecure:
        print('Need to add insecure-registry to docker.json on your all nodes.', file=sys.stderr)
        print('/etc/docker/daemon.json:', file=sys.stderr)
        print(f'  \"insecure-registries\": [\"{registry_address}\"]', file=sys.stderr)

    return config


def set_default(name):
    config = OmegaConf.create({'target': f'{DIR_PATH}/{name}.yml'})
    OmegaConf.save(config=config, f=f'{MLAD_HOME_PATH}/target.yml')
    return config


def _parse_datastore(kind, initializer, finalizer, prompts):
    config = initializer()
    for k, v in prompts.items():
        config[k] = utils.prompt(v, config[k])
    config = finalizer(config)
    return OmegaConf.from_dotlist([
        f'datastore.{kind}.{k}={v}' for k, v in config.items()
    ])


def _s3_initializer():
    # specific controlling docker
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


def _s3_finalizer(datastore):
    parsed = utils.parse_url(datastore['endpoint'])
    datastore['endpoint'] = parsed['url']
    datastore['verify'] = parsed['scheme'] == 'https'
    return datastore


def _datastore_s3_translator(kind, key, value):
    if key == 'endpoint':
        return f'S3_ENDPOINT={value}'
    elif key == 'verify':
        return [f'S3_USE_HTTPS={1 if value else 0}', 'S3_VERIFY_SSL=0']
    elif key == 'accesskey':
        return f'AWS_ACCESS_KEY_ID={value}'
    elif key == 'secretkey':
        return f'AWS_SECRET_ACCESS_KEY={value}'
    elif key == 'region':
        return f'AWS_REGION={value}'
    else:
        return f'{kind.upper()}_{key.upper()}={value}'


def _db_initializer():
    # specific controlling docker
    service_addr = utils.get_advertise_addr()
    mongo_port = utils.get_default_service_port('mlad_mongodb', 27017)
    if mongo_port:
        address = f'mongodb://{service_addr}:{mongo_port}'
    else:
        address = 'mongodb://localhost:27017'
    return {'address': address, 'username': '', 'password': ''}


def _db_finalizer(datastore):
    parsed = utils.parse_url(datastore['address'])
    datastore['address'] = f'mongodb://{parsed["address"]}'
    return datastore
