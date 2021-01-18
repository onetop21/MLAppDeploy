import sys
import os
import copy
import time
import uuid
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field
import docker
import requests
from docker.types import LogConfig
from mlad.core import exception
from mlad.core.libs import utils
from mlad.core.docker.logs import LogHandler, LogCollector
from mlad.core.default import project_service as service_default

HOME = str(Path.home())
CONFIG_PATH = HOME + '/.mlad'
SHORT_LEN = 10

# Docker CLI from HOST
def get_docker_client():
    config = utils.read_config()
    # docker.client.DockerClient
    return docker.from_env(environment={'DOCKER_HOST': config['docker']['host']})

# Manage Project and Network
def make_base_labels(workspace, username, project):
    config = utils.read_config()
    #workspace = f"{hostname}:{workspace}"
    # Server Side Config 에서 가져올 수 있는건 직접 가져온다.
    ## docker.host
    ## docker.registry
    project_key = utils.project_key(workspace)
    registry = config['docker']['registry']
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
        "image": labels['MLAD.PROJECT.IMAGE'],
    }

def is_swarm_mode(network):
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    return network.attrs['Driver'] == 'overlay'

def create_project_network(cli, base_labels, swarm=True, allow_reuse=False):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    #workspace = utils.get_workspace()
    driver = 'overlay' if swarm else 'bridge'
    project_key = base_labels['MLAD.PROJECT']
    network = get_project_network(cli, project_key=project_key)
    if network:
        if allow_reuse:
            yield {"result": 'succeed', 'output': network}
            return
        raise exception.AlreadyExist('Already exist project network.')
    basename = base_labels['MLAD.PROJECT.BASE']
    project_version = base_labels['MLAD.PROJECT.VERSION']
    #inspect_image(_) for _ in get_images(cli, project_key)
    default_image = base_labels['MLAD.PROJECT.IMAGE']

    # Create Docker Network
    network_name = f"{basename}-{driver}"
    try:
        message = f"Create project network [{network_name}]..."
        yield {'stream': message}
        labels = copy.deepcopy(base_labels)
        labels.update({
            'MLAD.PROJECT.NETWORK': network_name, 
            'MLAD.PROJECT.ID': str(utils.generate_unique_id()),
        })

        if driver == 'overlay':
            for _ in range(0, 255, 4):
                subnet = f'10.0.{_}.0/22'
                ipam_pool = docker.types.IPAMPool(subnet=subnet)
                ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
                network = cli.networks.create(
                    network_name, 
                    labels=labels,
                    driver='overlay', 
                    ipam=ipam_config, 
                    ingress=False)
                if network.attrs['Driver']: 
                    message = f'Selected Subnet [{subnet}]'
                    yield {'stream': message}
                    break
                network.remove()
        else:
            network = cli.networks.create(
                network_name, 
                labels=labels,
                driver='bridge')
        yield {"result": 'succeed', 'output': network}
    except docker.errors.APIError as e:
        message = f"Failed to create network.\n{e}"
        yield {'result': 'failed', 'stream': message}

def remove_project_network(cli, network, timeout=0xFFFF):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    network_info = inspect_project_network(network)
    network.remove()
    removed = False
    for tick in range(timeout):
        if not get_project_network(cli, project_key=network_info['key'].hex):
            removed = True
            break
        else:
            message = f"\033[1A\033[KWait to remove network [{tick}s]"
            #print(message, end="\r")
            yield {'stream': message}
            time.sleep(1)
    if not removed:
        message = f"Failed to remove network."
        #print(message, file=sys.stderr)
        yield {'status': 'failed', 'stream': message}
        #return False
    else:
        yield {'status': 'succeed'}
        #return True

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
        env = utils.get_service_env()
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
        env = utils.get_service_env()
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
        instance = cli.services.create(
            name=inst_name,
            #hostname=f'{name}.{{{{.Task.Slot}}}}',
            image=image, 
            env=env + ['TASK_ID={{.Task.ID}}', f'TASK_NAME={name}.{{{{.Task.Slot}}}}', 'NODE_HOSTNAME={{.Node.Hostname}}'],
            mounts=['/etc/timezone:/etc/timezone:ro', '/etc/localtime:/etc/localtime:ro'],
            command=command,
            container_labels=labels,
            labels=labels,
            networks=[{'Target': network.name, 'Aliases': [name]}],
            restart_policy=restart_policy,
            resources=resources,
            mode=service_mode,
            constraints=constraints
        )
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
            
def build_image(cli, base_labels, project, working_dir, tar, registry=None):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    # Setting path and docker file
    #os.getcwd() + "/.mlad/"
    #temporary
    PROJECT_CONFIG_PATH = utils.getProjectConfigPath(project)
    username = base_labels['MLAD.PROJECT.USERNAME']
    project_name = base_labels['MLAD.PROJECT.NAME']
    latest_name = base_labels['MLAD.PROJECT.IMAGE']

    PROJECT_CONFIG_PATH = f"{utils.CONFIG_PATH}/{username}/{project_name}"
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'
    DOCKERIGNORE_FILE = working_dir + '/.dockerignore'

    # extract tar to /tmp/mlad/latest_name
    # build image
    ## Ref : https://docs.docker.com/engine/api/v1.41/#operation/ImageBuild
    # POST /build

    build_output = cli.api.build(
        path=working_dir,
        tag=latest_name,
        dockerfile=DOCKERFILE_FILE,
        labels=base_labels,
        forcerm=True,
        decode=True
    )
    try:
        image = (cli.images.get(latest_name), build_output)
    except docker.errors.APIError:
        image = (None, build_output)
    return image

def remove_image(cli, ids, force=False):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    return [ cli.images.remove(image=id, force=force) for id in ids ]

def prune_images(cli, project_key=None):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    filters = 'MLAD.PROJECT'
    if project_key: filters+= f'={project_key}'
    return cli.images.prune(filters={ 'label': filters, 'dangling': True } )

def push_images(cli, project_key):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
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
 
def get_nodes(cli):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    return dict([(_.short_id, _) for _ in cli.nodes.list()])

def get_node(cli, node_key):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    return cli.nodes.get(node_key)

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
        print(f'Cannot find node "{node_key}"', file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'active'
    node.update(spec)
    
def disable_node(cli, node_key):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    try:
        node = cli.nodes.get(node_key)
    except docker.errors.APIError as e:
        print(f'Cannot find node "{node_key}"', file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'drain'
    node.update(spec)
    
def add_node_labels(cli, node_key, **kv):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    try:
        node = cli.nodes.get(node_key)
    except docker.errors.APIError as e:
        print(f'Cannot find node "{node_key}"', file=sys.stderr)
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
        sys.exit(1)
    spec = node.attrs['Spec']
    for key in keys:
        del spec['Labels'][key]
    node.update(spec)

def container_logs(cli, project_key, tail='all', follow=False, timestamps=False):
    config = utils.read_config()

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
    config = utils.read_config()

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
                yield message['stream']
    else:
        print('Cannot find running containers.', file=sys.stderr)
    handler.release()

















# for Command Line Interface (Local)
def image_build(project, workspace, tagging=False, verbose=False):
    config = utils.read_config()
    cli = get_docker_client()

    PROJECT_CONFIG_PATH = utils.getProjectConfigPath(project)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'
    DOCKERIGNORE_FILE = utils.getWorkingDir() + '/.dockerignore'

    base_labels = make_base_labels(utils.get_workspace(), config['account']['username'], project)
    project_key = base_labels['MLAD.PROJECT']
    project_version = base_labels['MLAD.PROJECT.VERSION']

    # Check latest image
    latest_image = None
    commit_number = 1
    images = get_images(cli, project_key)
    if len(images):
        latest_image = sorted(filter(None, [ image if tag.endswith('latest') else None for image in images for tag in image.tags ]), key=lambda x: str(x))
        if latest_image and len(latest_image): latest_image = latest_image[0]
        tags = sorted(filter(None, [ tag if not tag.endswith('latest') else None for image in images for tag in image.tags ]))
        if len(tags): commit_number=int(tags[-1].split('.')[-1])+1
    image_version = f'{project_version}.{commit_number}'

    # Generate dockerignore
    with open(DOCKERIGNORE_FILE, 'w') as f:
        f.write('\n'.join(workspace['ignore']))

    # Docker build
    try:
        image = build_image(cli, base_labels, project, utils.getWorkingDir(), None, config['docker']['registry'])

        # Print build output
        for _ in image[1]:
            if 'error' in _:
                raise docker.errors.BuildError(_['error'], None)
            elif 'stream' in _:
                if verbose: sys.stdout.write(_['stream'])

    except docker.errors.BuildError as e:
        print(e, file=sys.stderr)
        # Remove dockerignore
        os.unlink(DOCKERIGNORE_FILE)
        sys.exit(1)
    except docker.errors.APIError as e:
        print(e, file=sys.stderr)
        # Remove dockerignore
        os.unlink(DOCKERIGNORE_FILE)
        sys.exit(1)

    # Remove dockerignore
    os.unlink(DOCKERIGNORE_FILE)

    # Check duplicated.
    tagged = False
    if latest_image != image[0]:
        if tagging:
            image[0].tag(repository, tag=image_version)
            tagged = True
        if latest_image and len(latest_image.tags) < 2 and latest_image.tags[-1].endswith(':latest'):
            latest_image.tag('remove')
            cli.images.remove('remove')
    else:
        if tagging and len(latest_image.tags) < 2:
            image[0].tag(repository, tag=image_version)
            tagged = True
        else:
            print('Already built project to image.', file=sys.stderr)

    if tagged:
        return f"{'/'.join(repository.split('/')[1:])}:{image_version}"
    else:
        return None
