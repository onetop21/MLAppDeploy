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
    port = parsed_url.port

    # token
    user_token = input(f"MLAppDeploy User Token : ")

    # Registry
    registry_address = input(f"Docker Registry Host [docker.io]: ")

    # specific controlling docker
    s3_address = input(f'S3 Compatible Address [https://s3.amazonaws.com]: ') or 'https://s3.amazonaws.com'
    verifySSL = s3_address.startswith('https://')
    region = input('Region [us-east-1]: ') or 'us-east-1'
    access_key = input('Access Key ID: ')
    secret_key = input('Secret Access Key: ')
        
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

def set(*args):
    config = default_config['remote'](utils.read_config())
    config = OmegaConf.merge(config, OmegaConf.from_dotlist(args))
    utils.write_config(config)

def get(keys):
    config = default_config['remote'](utils.read_config())
    data = get_value(OmegaConf.to_container(config, resolve=True), keys)
    if isinstance(data, list):
        table = [["KEY", "VALUE"]]
        for key, value in data:
            if key: table.append([key, str(value)])
        utils.print_table(table)
    else:
        print(data)

def env(unset):
    config = default_config['remote'](utils.read_config())
    envs = utils.get_service_env(config)
    for line in envs:
        if unset:
            K, V = line.split('=')
            print(f'export {K}=')
        else:
            print(f'export {line}')
    print(f'# To set environment variables, run "eval $(mlad config env)"')
