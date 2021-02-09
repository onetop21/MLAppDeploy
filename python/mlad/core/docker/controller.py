import sys
import copy
import time
import json
import uuid
import base64
from pathlib import Path
from typing import Dict, List
import docker
import requests
import requests_unixsocket
from docker.types import LogConfig
from mlad.core import exception
from mlad.core.libs import utils
from mlad.core.docker.logs import LogHandler, LogCollector
from mlad.core.default import project_service as service_default

HOME = str(Path.home())
CONFIG_PATH = HOME + '/.mlad'
SHORT_LEN = 10

# Docker CLI from HOST
def get_docker_client(host='unix:///var/run/docker.sock'):
    # docker.client.DockerClient
    return docker.from_env(environment={'DOCKER_HOST': host})

# Manage Project and Network
def make_base_labels(workspace, username, project, registry):
    #workspace = f"{hostname}:{workspace}"
    # Server Side Config 에서 가져올 수 있는건 직접 가져온다.
    project_key = utils.project_key(workspace)
    basename = f"{username}-{project['name'].lower()}-{project_key[:SHORT_LEN]}"
    default_image = f"{utils.get_repository(basename, registry)}:latest"
    labels = {
        'MLAD.VERSION': '1',
        'MLAD.PROJECT': project_key,
        'MLAD.PROJECT.WORKSPACE': workspace,
        'MLAD.PROJECT.USERNAME': username,
        'MLAD.PROJECT.NAME': project['name'].lower(),
        'MLAD.PROJECT.AUTHOR': project['author'],
        'MLAD.PROJECT.VERSION': project['version'].lower(),
        'MLAD.PROJECT.BASE': basename,
        'MLAD.PROJECT.IMAGE': default_image,
    }
    return labels

def get_auth_headers(cli, image_name=None, auth_configs=None):
    if image_name:
        if not auth_configs:
            # docker.auth.get_config_header(client, registry)
            registry, repo_name = docker.auth.resolve_repository_name(image_name)
            header = docker.auth.get_config_header(cli.api, registry)
            if header:
                return {'X-Registry-Auth': header}
            else:
                return {'X-Registry-Auth': ''}
        else:
            if isinstance(auth_configs, str): 
                auth_configs = utils.decode_dict(auth_configs)
            registry, repo_name = docker.auth.resolve_repository_name(image_name)
            auth_config = docker.auth.resolve_authconfig({'auths': auth_configs}, registry)
            return {'X-Registry-Auth': docker.auth.encode_header(auth_config)}
    else:
        headers = {'X-Registry-Config': b''}
        docker.api.build.BuildApiMixin._set_auth_headers(cli.api, headers)
        return headers
    # get_all_auth_header(): -> docker.api.build.BuildApiMixin._set_auth_headers(self, headers)
    # or cli.api._auth_configs.get_all_credentials() -> JSON(X-Registry-Config)
    # and docker.auth.encode_header(JSON) -> X-Registry-Config or X-Registry-Auth

def get_project_networks(cli):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    networks = cli.networks.list(filters={'label':f"MLAD.PROJECT"})
    return dict([(_.name, _) for _ in networks])

def get_project_network(cli, **kwargs):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    if kwargs.get('project_key'):
        networks = cli.networks.list(filters={'label':f"MLAD.PROJECT={kwargs.get('project_key')}"})
    elif kwargs.get('project_id'):
        networks = cli.networks.list(filters={'label':f"MLAD.PROJECT.ID={kwargs.get('project_id')}"})
    elif kwargs.get('network_id'):
        networks = [cli.networks.get(kwargs.get('network_id'))]
    else:
        raise TypeError('At least one parameter is required.')
    if len(networks) == 1:
        return networks[0]
    elif len(networks) == 0:
        return None
    else:
        raise exception.Duplicated(f"Need to remove networks or down project, because exists duplicated networks.")

def get_labels(obj):
    if isinstance(obj, docker.models.networks.Network):
        return obj.attrs['Labels']
    elif isinstance(obj, docker.models.services.Service):
        return obj.attrs['Spec']['Labels']
    else:
        raise TypeError('Parameter is not valid type.')

def inspect_project_network(network):
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    labels = network.attrs['Labels']
    hostname, path = labels['MLAD.PROJECT.WORKSPACE'].split(':')
    return {
        'key': uuid.UUID(labels['MLAD.PROJECT']),
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': labels['MLAD.PROJECT.USERNAME'],
        'name': labels['MLAD.PROJECT.NETWORK'],
        'project': labels['MLAD.PROJECT.NAME'],
        'id': uuid.UUID(labels['MLAD.PROJECT.ID']),
        'version': labels['MLAD.PROJECT.VERSION'],
        'base': labels['MLAD.PROJECT.BASE'],
        'image': labels['MLAD.PROJECT.IMAGE'],
    }

def is_swarm_mode(network):
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    return network.attrs['Driver'] == 'overlay'

def create_project_network(cli, base_labels, extra_envs, swarm=True, allow_reuse=False, stream=False):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    #workspace = utils.get_workspace()
    driver = 'overlay' if swarm else 'bridge'
    project_key = base_labels['MLAD.PROJECT']
    network = get_project_network(cli, project_key=project_key)
    if network:
        if allow_reuse:
            if stream:
                def resp_stream():
                    yield {'result': 'exists', 'name': network.name, 'id': network.id}
                return resp_stream()
            else:
                stream_out = (_ for _ in resp_stream())
                return (network, stream_out)
        raise exception.AlreadyExist('Already exist project network.')
    basename = base_labels['MLAD.PROJECT.BASE']
    project_version = base_labels['MLAD.PROJECT.VERSION']
    #inspect_image(_) for _ in get_images(cli, project_key)
    default_image = base_labels['MLAD.PROJECT.IMAGE']

    # Create Docker Network
    def resp_stream():
        network_name = f"{basename}-{driver}"
        try:
            message = f"Create project network [{network_name}]...\n"
            yield {'stream': message}
            labels = copy.deepcopy(base_labels)
            labels.update({
                'MLAD.PROJECT.NETWORK': network_name, 
                'MLAD.PROJECT.ID': str(utils.generate_unique_id()),
                'MLAD.PROJECT.AUTH_CONFIGS': get_auth_headers(cli)['X-Registry-Config'].decode(),
                #'MLAD.PROJECT.AUTH_CONFIGS': get_auth_headers(cli)['X-Registry-Config'],
                'MLAD.PROJECT.ENV': utils.encode_dict(extra_envs),
            })
            print(labels)
            if driver == 'overlay':
                def address_range(bs=100, be=254, cs=0, ce=255, st=4):
                    for b in range(bs, be):
                        for c in range(cs, ce, st):
                            yield b, c
                for b, c, in address_range():
                    subnet = f'10.{b}.{c}.0/22'
                    ipam_pool = docker.types.IPAMPool(subnet=subnet)
                    ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
                    network = cli.networks.create(
                        network_name, 
                        labels=labels,
                        driver='overlay', 
                        ipam=ipam_config, 
                        ingress=False)
                    time.sleep(.1)
                    network.reload()
                    if network.attrs['Driver']: 
                        message = f'Selected Subnet [{subnet}]\n'
                        yield {'stream': message}
                        break
                    network.remove()
            else:
                network = cli.networks.create(
                    network_name, 
                    labels=labels,
                    driver='bridge')
            if network.attrs['Driver']:
                yield {"result": 'succeed', 'name': network_name, 'id': network.id}
            else:
                yield {"result": 'failed', 'stream': 'Cannot find suitable subnet.\n'}
        except docker.errors.APIError as e:
            message = f"Failed to create network.\n{e}\n"
            yield {'result': 'failed', 'stream': message}
    if stream:
        return resp_stream()
    else:
        stream_out = (_ for _ in resp_stream())
        return (get_project_network(cli, project_key=project_key), stream_out)

def remove_project_network(cli, network, timeout=0xFFFF, stream=False):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    network_info = inspect_project_network(network)
    network.remove()
    def resp_stream():
        removed = False
        for tick in range(timeout):
            if not get_project_network(cli, project_key=network_info['key'].hex):
                removed = True
                break
            else:
                padding = '\033[1A\033[K' if tick else ''
                message = f"{padding}Wait to remove network [{tick}s]\n"
                yield {'stream': message}
                time.sleep(1)
        if not removed:
            message = f"Failed to remove network.\n"
            #print(message, file=sys.stderr)
            yield {'result': 'failed', 'stream': message}
            #return False
        else:
            yield {'result': 'succeed'}
            #return True
    if stream:
        return resp_stream()
    else:
        return (not get_project_network(cli, project_key=network_info['key'].hex), (_ for _ in resp_stream()))


# Manage services and tasks
def get_containers(cli, project_key=None, extra_filters={}):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    filters = [f'MLAD.PROJECT={project_key}' if project_key else 'MLAD.PROJECT']
    filters += [f'{key}={value}' for key, value in extra_filters.items()]
    services = cli.containers.list(filters={'label': filters})
    if project_key:
        return dict([(_.attrs['Config']['Labels']['MLAD.PROJECT.SERVICE'], _) for _ in services])
    else:
        return dict([(_.name, _) for _ in services])

def get_services(cli, project_key=None, extra_filters={}):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    filters = [f'MLAD.PROJECT={project_key}' if project_key else 'MLAD.PROJECT']
    filters += [f'{key}={value}' for key, value in extra_filters.items()]
    services = cli.services.list(filters={'label': filters})
    if project_key:
        return dict([(_.attrs['Spec']['Labels']['MLAD.PROJECT.SERVICE'], _) for _ in services])
    else:
        return dict([(_.name, _) for _ in services])

def get_service(cli, service_id):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    return cli.services.get(service_id)

def inspect_container(container):
    if not isinstance(container, docker.models.containers.Container): raise TypeError('Parameter is not valid type.')
    labels = container.attrs['Config']['Labels']
    hostname, path = labels.get('MLAD.PROJECT.WORKSPACE', ':').split(':')
    inspect = {
        'key': uuid.UUID(labels['MLAD.PROJECT']) if labels.get('MLAD.VERSION') else '',
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': labels.get('MLAD.PROJECT.USERNAME'),
        'network': labels.get('MLAD.PROJECT.NETWORK'),
        'project': labels.get('MLAD.PROJECT.NAME'),
        'project_id': uuid.UUID(labels['MLAD.PROJECT.ID']) if labels.get('MLAD.VERSION') else '',
        'version': labels.get('MLAD.PROJECT.VERSION'),
        'base': labels.get('MLAD.PROJECT.BASE'),
        'image': container.attrs['Config']['Image'], #labels['MLAD.PROJECT.IMAGE'],

        'id': container.id,
        'name': labels.get('MLAD.PROJECT.SERVICE'),
        'ports': {}
    }
    if 'PortBindings' in container.attrs['HostConfig'] and container.attrs['HostConfig']['PortBindings']:
        for target, host in container.attrs['HostConfig']['PortBindings'].items():
            published = ', '.join([f"{_['HostIp']}:{_['HostPort']}" for _ in host])
            inspect['ports'][f"{target}->{published}"] = {
                'target': target,
                'published': published
            }
    return inspect

def inspect_service(service):
    if not isinstance(service, docker.models.services.Service): raise TypeError('Parameter is not valid type.')
    labels = service.attrs['Spec']['Labels']
    hostname, path = labels.get('MLAD.PROJECT.WORKSPACE', ':').split(':')
    inspect = {
        'key': uuid.UUID(labels['MLAD.PROJECT']) if labels.get('MLAD.VERSION') else '',
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': labels.get('MLAD.PROJECT.USERNAME'),
        'network': labels.get('MLAD.PROJECT.NETWORK'),
        'project': labels.get('MLAD.PROJECT.NAME'),
        'project_id': uuid.UUID(labels['MLAD.PROJECT.ID']) if labels.get('MLAD.VERSION') else '',
        'version': labels.get('MLAD.PROJECT.VERSION'),
        'base': labels.get('MLAD.PROJECT.BASE'),
        'image': service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'], # Replace from labels['MLAD.PROJECT.IMAGE']

        'id': service.id,
        'name': labels.get('MLAD.PROJECT.SERVICE'), 
        'replicas': service.attrs['Spec']['Mode']['Replicated']['Replicas'],
        'tasks': dict([(task['ID'][:SHORT_LEN], task) for task in service.tasks()]),
        'ports': {}
    }
    if 'Ports' in service.attrs['Endpoint']:
        for _ in service.attrs['Endpoint']['Ports']:
            target = _['TargetPort']
            published = _['PublishedPort']
            inspect['ports'][f"{target}->{published}"] = {
                'target': target,
                'published': published
            }
    return inspect

def create_containers(cli, network, services, extra_labels={}):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    project_info = inspect_project_network(network)
    network_labels = get_labels(network)
    swarm_mode = is_swarm_mode(network)
    
    # Update Project Name
    project_info = inspect_project_network(network)
    image_name = project_info['image']
    project_base = project_info['base']

    instances = []
    for name in services:
        service = service_default(services[name])

        # Check running already
        if get_containers(cli, project_info['key'], extra_filters={'MLAD.PROJECT.SERVICE': name}):
            raise exception.Duplicated('Already running container.')

        image = service['image'] or image_name
        env = utils.decode_dict(network_labels.get('MLAD.PROJECT.ENV'))
        env += [f"TF_CPP_MIN_LOG_LEVEL=3"]
        env += [f"PROJECT={project_info['project']}"]
        env += [f"USERNAME={project_info['username']}"]
        env += [f"PROJECT_KEY={project_info['key']}"]
        env += [f"PROJECT_ID={project_info['id']}"]
        env += [f"SERVICE={name}"]
        env += [f"{key}={service['env'][key]}" for key in service['env'].keys()]
        command = service['command'] + service['arguments']
        labels = copy.copy(network_labels)
        labels.update(extra_labels)
        labels['MLAD.PROJECT.SERVICE'] = name
        
        # Try to run
        inst_name = f"{project_base}-{name}"
        instance = cli.containers.run(
            image, 
            command=command,
            name=inst_name,
            environment=env,
            labels=labels,
            runtime='runc',
            restart_policy={'Name': 'on-failure', 'MaximumRetryCount': 1},
            detach=True,
        )
        network.connect(instance, aliases=[name])
        instances.append(instance)
    return instances


def create_services(cli, network, services, extra_labels={}):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    project_info = inspect_project_network(network)
    network_labels = get_labels(network)
    swarm_mode = is_swarm_mode(network)
    
    # Update Project Name
    project_info = inspect_project_network(network)
    image_name = project_info['image']
    project_base = project_info['base']

    instances = []
    for name in services:
        service = service_default(services[name])

        # Check running already
        if get_services(cli, project_info['key'], extra_filters={'MLAD.PROJECT.SERVICE': name}):
            raise exception.Duplicated('Already running service.')

        image = service['image'] or image_name
        env = utils.decode_dict(network_labels.get('MLAD.PROJECT.ENV'))
        env += [f"TF_CPP_MIN_LOG_LEVEL=3"]
        env += [f"PROJECT={project_info['project']}"]
        env += [f"USERNAME={project_info['username']}"]
        env += [f"PROJECT_KEY={project_info['key']}"]
        env += [f"PROJECT_ID={project_info['id']}"]
        env += [f"SERVICE={name}"]
        env += [f"{key}={service['env'][key]}" for key in service['env'].keys()]
        command = service['command'] + service['arguments']
        labels = copy.copy(network_labels)
        labels.update(extra_labels)
        labels['MLAD.PROJECT.SERVICE'] = name
        
        policy = service['deploy']['restart_policy']
        # Convert Human-readable to nanoseconds ns|us|ms|s|m|h
        if policy['delay']:
            converted = policy['delay']
            timeinfo = str(converted).lower()
            if timeinfo.endswith('ns'):
                converted = int(timeinfo[:-2]) * 1
            elif timeinfo.endswith('us'):
                converted = int(timeinfo[:-2]) * 1000
            elif timeinfo.endswith('ms'):
                converted = int(timeinfo[:-2]) * 1000000
            elif timeinfo.endswith('s'):
                converted = int(timeinfo[:-1]) * 1000000000
            elif timeinfo.endswith('m'):
                converted = int(timeinfo[:-1]) * 1000000000 * 60
            elif timeinfo.endswith('h'):
                converted = int(timeinfo[:-1]) * 1000000000 * 60 * 60
            policy['delay'] = converted
        if policy['window']:
            converted = policy['window']
            timeinfo = str(converted).lower()
            if timeinfo.endswith('ns'):
                converted = int(timeinfo[:-2]) * 1
            elif timeinfo.endswith('us'):
                converted = int(timeinfo[:-2]) * 1000
            elif timeinfo.endswith('ms'):
                converted = int(timeinfo[:-2]) * 1000000
            elif timeinfo.endswith('s'):
                converted = int(timeinfo[:-1]) * 1000000000
            elif timeinfo.endswith('m'):
                converted = int(timeinfo[:-1]) * 1000000000 * 60
            elif timeinfo.endswith('h'):
                converted = int(timeinfo[:-1]) * 1000000000 * 60 * 60
            policy['window'] = converted

        restart_policy = docker.types.RestartPolicy(
            condition=policy['condition'], 
            delay=policy['delay'], 
            max_attempts=policy['max_attempts'], 
            window=policy['window']
        )
        resources = docker.types.Resources()
        service_mode = docker.types.ServiceMode('replicated')
        constraints = []

        # Resource Spec
        res_spec = {}
        if 'cpus' in service['deploy']['quotes']: 
            res_spec['cpu_limit'] = service['deploy']['quotes']['cpus'] * 1000000000
            res_spec['cpu_reservation'] = service['deploy']['quotes']['cpus'] * 1000000000
        if 'mems' in service['deploy']['quotes']: 
            data = str(service['deploy']['quotes']['mems'])
            size = int(data[:-1])
            unit = data.lower()[-1:]
            if unit == 'g':
                size *= (2**30)
            elif unit == 'm':
                size *= (2**20)
            elif unit == 'k':
                size *= (2**10)
            res_spec['mem_limit'] = size
            res_spec['mem_reservation'] = size
        if 'gpus' in service['deploy']['quotes']:
            if service['deploy']['quotes']['gpus'] > 0:
                res_spec['generic_resources'] = { 'gpu': service['deploy']['quotes']['gpus'] }
            else: 
                env += ['NVIDIA_VISIBLE_DEVICES=void']
        resources = docker.types.Resources(**res_spec)
        service_mode = docker.types.ServiceMode('replicated', replicas=service['deploy']['replicas'])
        constraints = [
            f"node.{key}=={str(service['deploy']['constraints'][key])}" for key in service['deploy']['constraints']
        ]

        # Try to run
        inst_name = f"{project_base}-{name}"
        kwargs = {
            'name': inst_name,
            #hostname=f'{name}.{{{{.Task.Slot}}}}',
            'image': image, 
            'env': env + ['TASK_ID={{.Task.ID}}', f'TASK_NAME={name}.{{{{.Task.Slot}}}}', 'NODE_HOSTNAME={{.Node.Hostname}}'],
            'mounts': ['/etc/timezone:/etc/timezone:ro', '/etc/localtime:/etc/localtime:ro'],
            'command': command,
            'container_labels': labels,
            'labels': labels,
            'networks': [{'Target': network.name, 'Aliases': [name]}],
            'restart_policy': restart_policy,
            'resources': resources,
            'mode': service_mode,
            'constraints': constraints
        }
        #instance = cli.services.create(**kwargs)

        ## Create Service by REST API (with AuthConfig)
        #params = 
        auth_configs = utils.decode_dict(network_labels.get('MLAD.PROJECT.AUTH_CONFIGS'))
        headers = get_auth_headers(cli, image, auth_configs) if auth_configs else get_auth_headers(cli, image)
        #headers['Content-Type'] = 'application/json'
        body = utils.change_key_style(docker.models.services._get_create_service_kwargs('create', kwargs))
        #import pprint
        #pprint.pprint(body)
        host = utils.get_requests_host(cli)
        with requests_unixsocket.post(f"{host}/v1.40/services/create", headers=headers, json=body) as resp:
            if resp.status_code == 201:
                instance = get_service(cli, inst_name)
            else:
                print(resp.text, file=sys.stderr)
                instance = None
        instances.append(instance)
    return instances

def remove_containers(cli, containers):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    for container in containers:
        print(f"Stop {container.name}...")
        container.stop()
    for container in containers:
        container.wait()
        container.remove()
    return True

def remove_services(cli, services, timeout=0xFFFF):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    for service in services:
        inspect = inspect_service(service)
        print(f"Stop {inspect['name']}...")
        service.remove()
    removed = True
    for service in services:
        service_removed = False
        for _ in range(timeout):
            try:
                service.reload()
            except docker.errors.NotFound:
                service_removed = True
                break
            time.sleep(1)
        removed &= service_removed
    return removed

# Image Control
def get_images(cli, project_key=None):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')

    filters = 'MLAD.PROJECT'
    if project_key: filters+= f"={project_key}"
    return cli.images.list(filters={ 'label': filters } )

def get_image(cli, image_id):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    return cli.images.get(image_id)    

def inspect_image(image):
    if not isinstance(image, docker.models.images.Image): raise TypeError('Parameter is not valid type.')
    sorted_tags = sorted(image.tags, key=lambda x: chr(0xFFFF) if x.endswith('latest') else x)
    headed = False
    if sorted_tags:
        latest_tag = sorted_tags[-1]
        repository, tag = latest_tag.rsplit(':', 1) if ':' in latest_tag else (latest_tag, '')
        headed = latest_tag.endswith('latest')
    else:
        repository, tag = image.short_id.split(':',1)[-1], ''
    labels = {
        # for Image
        'id': image.id.split(':',1)[-1],
        'short_id': image.short_id.split(':',1)[-1],
        'repository': repository,
        'tag': tag,
        'tags': image.tags,
        'latest': headed,
        'author': image.attrs['Author'],
        'created': image.attrs['Created'],
        # for Project
        'workspace': image.labels['MLAD.PROJECT.WORKSPACE'] if 'MLAD.PROJECT.WORKSPACE' in image.labels else 'Not Supported',
        'project_name': image.labels['MLAD.PROJECT.NAME'],
    }
    return labels

def build_image(cli, base_labels, tar, dockerfile, stream=False):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    # Setting path and docker file
    #os.getcwd() + "/.mlad/"
    #temporary
    project_base = base_labels['MLAD.PROJECT.BASE']
    project_name = base_labels['MLAD.PROJECT.NAME']
    username = base_labels['MLAD.PROJECT.USERNAME']
    latest_name = base_labels['MLAD.PROJECT.IMAGE']

    headers = get_auth_headers(cli)
    headers['content-type'] = 'application/x-tar'

    params = {
        'dockerfile': dockerfile,
        't': latest_name,
        'labels': json.dumps(base_labels),
        'forcerm': 1,
    }
    host = utils.get_requests_host(cli)
    def _request_build(headers, params, tar):
        with requests_unixsocket.post(f"{host}/v1.24/build", headers=headers, params=params, data=tar, stream=True) as resp:
            for _ in resp.iter_lines(decode_unicode=True):
                line = json.loads(_)
                yield line
    if stream:
        return _request_build(headers, params, tar)
    else:
        resp_stream = (_ for _ in _request_build(headers, params, tar))
        for _ in resp_stream:
            if 'error' in _: return (None, resp_stream)
        return (get_image(cli, latest_name), resp_stream)

def remove_image(cli, ids, force=False):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    return [ cli.images.remove(image=id, force=force) for id in ids ]

def prune_images(cli, project_key=None):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    filters = 'MLAD.PROJECT'
    if project_key: filters+= f'={project_key}'
    return cli.images.prune(filters={ 'label': filters, 'dangling': True } )

def push_images(cli, project_key, stream=False):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    def _request_push():
        for _ in get_images(cli, project_key):
            inspect = inspect_image(_)
            if inspect['short_id'] == inspect['repository']: continue
            repository = inspect['repository']
            output = cli.images.push(repository, stream=True, decode=True)
            try:
                for stream in output:
                    yield stream
            except StopIteration:
                pass
    if stream:
        return _request_push()
    else:
        resp_stream = (_ for _ in _request_push())
        for _ in resp_stream:
            if 'error' in _: return (False, resp_stream)
        return (True, resp_stream)

 
def get_nodes(cli):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    return dict([(_.short_id, _) for _ in cli.nodes.list()])

def get_node(cli, node_key):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    try:
        node = cli.nodes.get(node_key)
    except docker.errors.APIError as e:
        #print(f'Cannot find node "{node_key}"', file=sys.stderr)
        raise exception.NotFound(f'Cannot find node "{node_key}"')
    return node

def inspect_node(node):
    if not isinstance(node, docker.models.nodes.Node): raise TypeError('Parameter is not valid type.')
    return {
        'id': node.attrs['ID'],
        'hostname': node.attrs['Description']['Hostname'],
        'labels': node.attrs['Spec']['Labels'],
        'role': node.attrs['Spec']['Role'],
        'availability': node.attrs['Spec']['Availability'],
        'platform': node.attrs['Description']['Platform'],
        'resources': node.attrs['Description']['Resources'],
        'engine_version': node.attrs['Description']['Engine']['EngineVersion'],
        'status': node.attrs['Status']
    }

def enable_node(cli, node_key):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    try:
        node = cli.nodes.get(node_key)
    except docker.errors.APIError as e:
        #print(f'Cannot find node "{node_key}"', file=sys.stderr)
        raise exception.NotFound(f'Cannot find node "{node_key}"')
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'active'
    node.update(spec)
    
def disable_node(cli, node_key):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    try:
        node = cli.nodes.get(node_key)
    except docker.errors.APIError as e:
        #print(f'Cannot find node "{node_key}"', file=sys.stderr)
        raise exception.NotFound(f'Cannot find node "{node_key}"')
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'drain'
    node.update(spec)
    
def add_node_labels(cli, node_key, **kv):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    try:
        node = cli.nodes.get(node_key)
    except docker.errors.APIError as e:
        #print(f'Cannot find node "{node_key}"', file=sys.stderr)
        raise exception.NotFound(f'Cannot find node "{node_key}"')
        sys.exit(1)
    spec = node.attrs['Spec']
    for key in kv:
        spec['Labels'][key] = kv[key]
    node.update(spec)

def remove_node_labels(cli, node_key, *keys):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    try:
        node = cli.nodes.get(node_key)
    except docker.errors.APIError as e:
        print(f'Cannot find node "{node_key}"', file=sys.stderr)
        raise exception.NotFound(f'Cannot find node "{node_key}"')
        sys.exit(1)
    spec = node.attrs['Spec']
    for key in keys:
        del spec['Labels'][key]
    node.update(spec)

def container_logs(cli, project_key, tail='all', follow=False, timestamps=False):
    instances = cli.containers.list(all=True, filters={'label': f'MLAD.PROJECT={project_key}'})
    logs = [ (inst.attrs['Config']['Labels']['MLAD.PROJECT.SERVICE'], inst.logs(follow=follow, tail=tail, timestamps=timestamps, stream=True)) for inst in instances ]
    if len(logs):
        with LogCollector() as collector:
            for name, log in logs:
                collector.add_iterable(log, name=name, timestamps=timestamps)
            for message in collector:
                yield message
    else:
        print('Cannot find running containers.', file=sys.stderr)

def get_project_logs(cli, project_key, tail='all', follow=False, timestamps=False, names_or_ids=[]):
    services = get_services(cli, project_key)
    selected = []
    sources = [(_['name'], f"/services/{_['id']}", _['tasks']) for _ in [inspect_service(_) for _ in services.values()]]
    if names_or_ids:
        selected = []
        for _ in sources:
            if _[0] in names_or_ids:
                selected.append(_[:2])
            else:
                selected += [(_[0], f"/tasks/{__}") for __ in _[2] if __ in names_or_ids]
    else:
        selected = [_[:2] for _ in sources]

    handler = LogHandler(cli)
    logs = [(service_name, handler.logs(target, details=True, follow=follow, tail=tail, timestamps=timestamps, stdout=True, stderr=True)) for service_name, target in selected]

    if len(logs):
        with LogCollector(release_callback=handler.close) as collector:
            for name, log in logs:
                collector.add_iterable(log, name=name, timestamps=timestamps)
            for message in collector:
                yield message
    else:
        print('Cannot find running containers.', file=sys.stderr)
    handler.release()

