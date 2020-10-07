import sys, os
from mladcli.libs import utils
from mladcli.default import config as default_config

def dict_to_graph(vars, base={}):
    def convert_type(value, tyidx=0):
        from distutils import util
        TYPES = [int, lambda x: bool(util.strtobool(x)), float]
        if tyidx < len(TYPES):
            try:
                value = TYPES[tyidx](value)
            except ValueError as e:
                value = convert_type(value, tyidx+1)
        return value
        # str to float
    config = base
    for ckeys in vars:
        keys = ckeys.split('.')
        head = config
        for key in keys[:-1]:
            head[key] = head[key] if key in head else {}
            head = head[key]
        if vars[ckeys]:
            head[keys[-1]] = convert_type(vars[ckeys])
        elif len(keys):
            if keys[-1] in head: del head[keys[-1]]
        else:
            if keys[-1] in config: del config[keys[-1]]
    return config

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

def init(username, address):
    if address.startswith('unix://'):
        docker_host = address
    elif ':' in address:
        docker_host = address
        address, docker_port = address.split(':')
    elif not address in ['localhost', '127.0.0.1']:
        docker_host = f'{address}:2375'
    else:
        docker_host = f'unix:///var/run/docker.sock'

    address = utils.get_advertise_addr() if docker_host.startswith('unix://') else address

    # specific controlling docker
    minio_port = utils.get_default_service_port('mlad_minio', 9000, docker_host)
    if minio_port: 
        s3_address = f'http://{address}:{minio_port}'
        verifySSL = False
        region = 'ap-northeast-2'
        print(f'Detected MinIO Server[{s3_address}] on MLAppDeploy[{docker_host}].')
        access_key = input('Access Key ID [MLAPPDEPLOY]: ') or 'MLAPPDEPLOY'
        secret_key = input('Secret Access Key [MLAPPDEPLOY]: ') or 'MLAPPDEPLOY'
    else:
        print(f'Failed to detect MinIO Server on MLAppDeploy[{docker_host}].')
        s3_address = input(f'S3 Compatible Address [https://s3.amazonaws.com]: ') or 'https://s3.amazonaws.com'
        verifySSL = s3_address.startswith('https://')
        region = input('Region [us-east-1]: ') or 'us-east-1'
        access_key = input('Access Key ID: ')
        secret_key = input('Secret Access Key: ')
        
    registry_port = utils.get_default_service_port('mlad_registry', 5000, docker_host)
    if registry_port:
        registry_address = f'{address}:{registry_port}'
        print(f'Detected Docker Registry[{registry_address}] on MLAppDeploy[{docker_host}].')
    else:
        registry_address = None
        print(f'Failed to detect Docker Registry on MLAppDeploy[{docker_host}].')
        print(f'Docker image will be shared by Docker Hub.')

    utils.generate_empty_config()
    set(*(
        f'account.username={username}', 
        f'docker.host={docker_host}',
        f'docker.registry={registry_address}',
        f'docker.wsl2={utils.is_host_wsl2(docker_host)}', 
        f's3.endpoint={s3_address}',
        f's3.verify={verifySSL}',
        f's3.region={region}',
        f's3.accesskey={access_key}',
        f's3.secretkey={secret_key}',
    ))
    get(None)

def set(*args):
    try:
        vars = dict([ var.split('=') for var in args ])
    except ValueError as e:
        print('Argument format is not valid.', file=sys.stderr)
        sys.exit(1)

    config = default_config(utils.read_config())
    config = dict_to_graph(vars, config)

    utils.write_config(config)

def get(keys):
    config = default_config(utils.read_config())
    data = get_value(config, keys)
    if isinstance(data, list):
        print('{:24} {:32}'.format('KEY', 'VALUE'))
        for key, value in data:
            #if key and value: print('{}={}'.format(key, value))
            if key: print('{:24} {:32}'.format(key, str(value)))
    else:
        print(data)

def env(unset):
    config = utils.get_service_env()
    for line in config:
        if unset:
            K, V = line.split('=')
            print(f'export {K}=')
        else:
            print(f'export {line}')
    print(f'# To set environment variables, run "eval $(mlad config env)"')
