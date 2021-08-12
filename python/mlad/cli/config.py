import sys
import os
import uuid
from omegaconf import OmegaConf
from getpass import getuser

from mlad.cli.libs import utils
from mlad.cli.libs import datastore as ds
from mlad.core.default import config as default_config


def get_value(config, keys, stack=[]):
    if not keys:
        data = []
        for key in config:
            if isinstance(config[key], dict):
                data = data + get_value(config[key], keys, stack + [key])
            else:
                data.append(('.'.join(stack + [key]), config[key]))
        return data
    else:
        head = config
        try:
            for key in keys.split('.'):
                stack.append(key)
                head = head[key]
            if not isinstance(head, dict):
                return head
            else:
                print('Value is expandable.', file=sys.stderr)
        except KeyError:
            print('Cannot find config key.', file=sys.stderr)
        sys.exit(1)


def init(address):
    # address
    address = utils.parse_url(address)['url']

    session = utils.create_session_key()

    # registry
    registry_address = 'https://docker.io'
    warn_insecure = False
    service_addr = utils.get_advertise_addr()
    registry_port = utils.get_default_service_port('mlad_registry', 5000)
    if registry_port:
        registry_address = f'http://{service_addr}:{registry_port}'
        #print(f'Detected Docker Registry[{registry_address}] on docker host.')
    registry_address = utils.prompt("Docker Registry Address", registry_address)
    parsed_url = utils.parse_url(registry_address)
    if parsed_url['scheme'] != 'https':
        warn_insecure = True
    registry_address = parsed_url['url']
    registry_namespace = utils.prompt("Docker Registry Namespace")
    utils.generate_empty_config()
    set(*(
        f"mlad.address={address}",
        f"mlad.session={session}",
        f'docker.registry.address={registry_address}',
        f'docker.registry.namespace={registry_namespace}'
    ))
    datastore()

    print('\nRESULT')
    get(None)

    if warn_insecure:
        print()
        print(f"Need to add insecure-registry to docker.json on your all nodes.", file=sys.stderr)
        print(f"/etc/docker/daemon.json:", file=sys.stderr)
        print(f"  \"insecure-registries\": [\"{registry_address}\"]", file=sys.stderr)


def set(*args):
    config = default_config['client'](utils.read_config())
    config = OmegaConf.merge(config, OmegaConf.from_dotlist(args))
    utils.write_config(config)


def get(keys, no_trunc=False):
    config = default_config['client'](utils.read_config())
    data = get_value(OmegaConf.to_container(config, resolve=True), keys)
    if isinstance(data, list):
        table = [["KEY", "VALUE"]]
        for key, value in data:
            if key: table.append([key, str(value)])
        utils.print_table(*([table, 'No have configuration values.'] + ([0] if no_trunc else [])))
    else:
        print(data)


def env(unset):
    config = default_config['client'](utils.read_config())
    envs = ds.get_env(config)
    for line in envs:
        if unset:
            K, V = line.split('=')
            print(f'export {K}=')
        else:
            print(f'export {line}')
    print(f'# To set environment variables, run "eval $(mlad config env)"')


# Extension for DataStore
def datastore(kind=None):
    if not kind:
        for _ in ds.datastores.keys():
            datastore(_)
        return
    else:
        if not kind in ds.datastores:
            print('Cannot support datastore type.', file=sys.stderr)
            print(f"Support DataStore Type [{', '.join(ds.datastores.keys())}]", file=sys.stderr)
            sys.exit(1)
    store = ds.datastores[kind]
    config = store['initializer']()
    for k, v in store['prompt'].items():
        config[k] = utils.prompt(v, config[k])
    config = store['finalizer'](config)    
    set(*[f"datastore.{kind}.{k}={v}" for k, v in config.items()])


# S3 DataStore
def _datastore_s3_initializer():
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


def _datastore_s3_finalizer(datastore):
    parsed = utils.parse_url(datastore['endpoint'])
    datastore['endpoint'] = parsed['url']
    datastore['verify'] = parsed['scheme'] == 'https'
    return datastore


def _datastore_s3_translator(kind, key, value):
    if key == 'endpoint':
        return f"S3_ENDPOINT={value}"
    elif key == 'verify':
        return [f"S3_USE_HTTPS={1 if value else 0}", f"S3_VERIFY_SSL=0"]
    elif key == 'accesskey':
        return f"AWS_ACCESS_KEY_ID={value}"
    elif key == 'secretkey':
        return f"AWS_SECRET_ACCESS_KEY={value}"
    elif key == 'region':
        return f"AWS_REGION={value}"
    else:
        return f"{kind.upper()}_{key.upper()}={value}"

ds.add_datastore('s3',
        _datastore_s3_initializer, 
        _datastore_s3_finalizer,
        _datastore_s3_translator,
        endpoint='S3 Compatible Address',
        region='Region',
        accesskey='Access Key ID',
        secretkey='Secret Access Key')


# MongoDB DataStore
def _datastore_mongodb_initializer():
    # specific controlling docker
    service_addr = utils.get_advertise_addr()
    mongo_port = utils.get_default_service_port('mlad_mongodb', 27017)
    if mongo_port:
        address = f"mongodb://{service_addr}:{mongo_port}"
    else:
        address = f"mongodb://localhost:27017"
    return {'address': address, 'username': '', 'password': ''}

def _datastore_mongodb_finalizer(datastore):
    parsed = utils.parse_url(datastore['address'])
    datastore['address'] = f"mongodb://{parsed['address']}"
    return datastore

ds.add_datastore('mongodb',
        _datastore_mongodb_initializer, 
        _datastore_mongodb_finalizer, 
        address='MongoDB Address',
        username='MongoDB Username',
        password='MongoDB Password')

