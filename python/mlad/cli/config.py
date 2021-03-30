import sys
import os
from urllib.parse import urlparse
from omegaconf import OmegaConf
from mlad.cli.libs import utils
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

def init(address, token):
    # Health Check?
    parsed_url = urlparse(address)
    scheme = parsed_url.scheme
    hostname = parsed_url.hostname
    port = parsed_url.port or (443 if scheme == 'https' else 80)

    # token
    user_token = input(f"MLAppDeploy User Token : ")

    # specific controlling docker
    service_addr = utils.get_advertise_addr()
    minio_port = utils.get_default_service_port('mlad_minio', 9000)
    if minio_port:
        s3_address = f'http://{service_addr}:{minio_port}'
        region = 'ap-northeast-2'
        access_key = 'MLAPPDEPLOY'
        secret_key = 'MLAPPDEPLOY'
        #print(f'Detected MinIO Server[{s3_address}] on docker host.')
    else:
        s3_address = 'https://s3.amazonaws.com'
        region = 'us-east-1'
        access_key = None
        secret_key = None
    s3_address = utils.prompt('S3 Compatible Address', s3_address)
    region = utils.prompt('Region', region)
    access_key = utils.prompt('Access Key ID', access_key)
    secret_key = utils.prompt('Secret Access Key', secret_key)
    verifySSL = s3_address.startswith('https://')

    registry_port = utils.get_default_service_port('mlad_registry', 5000)
    if registry_port:
        registry_address = f'{service_addr}:{registry_port}'
        warn_insecure = True
        #print(f'Detected Docker Registry[{registry_address}] on docker host.')
    else:
        registry_address = 'docker.io'
        warn_insecure = False
    registry_address = utils.prompt("Docker Registry Host", registry_address)
    registry_address = registry_address.split('//')[-1] # Remove Scheme
    
    utils.generate_empty_config()
    set(*(
        f"mlad.host={hostname}",
        f"mlad.port={port}",
        f"mlad.token.admin={token}",
        f"mlad.token.user={user_token}",
        f'docker.registry={registry_address}',
        f'environment.s3.endpoint={s3_address}',
        f'environment.s3.verify={verifySSL}',
        f'environment.s3.region={region}',
        f'environment.s3.accesskey={access_key}',
        f'environment.s3.secretkey={secret_key}',
    ))
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
    envs = utils.get_service_env(config)
    for line in envs:
        if unset:
            K, V = line.split('=')
            print(f'export {K}=')
        else:
            print(f'export {line}')
    print(f'# To set environment variables, run "eval $(mlad config env)"')
