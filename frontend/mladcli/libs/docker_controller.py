import sys
import os
import copy
import time
import uuid
from pathlib import Path
from datetime import datetime
from dateutil import parser
from typing import Dict, List
from dataclasses import dataclass, field
import docker
import requests
from docker.types import LogConfig
from mladcli import exception
from mladcli.libs import utils, interrupt_handler as InterruptHandler, logger_thread as LoggerThread

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

def get_project_networks(cli, project_key=None):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    networks = cli.networks.list(filters={'label':f"MLAD.PROJECT={project_key}"})
    if project_key:
        if len(networks) == 1:
            return networks[0]
        elif len(networks) == 0:
            return None
        else:
            raise exception.Duplicated(f"Need to remove networks or down project, because exists duplicated networks.")
    else:
        return dict([(_.name, _) for _ in networks])

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
    network = get_project_networks(cli, project_key)
    if network:
        if allow_reuse: return network
        raise exception.AlreadyExist('Already exist project network.')

    basename = base_labels['MLAD.PROJECT.BASE']
    project_version = base_labels['MLAD.PROJECT.VERSION']
    #inspect_image(_) for _ in get_images(cli, project_key)
    default_image = base_labels['MLAD.PROJECT.IMAGE']

    # Create Docker Network
    network_name = f"{basename}-{driver}"
    try:
        print('Create network...')
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
                    print(f'Selected Subnet [{subnet}]')
                    break
                network.remove()
        else:
            network = cli.networks.create(
                network_name, 
                labels=labels,
                driver='bridge')
    except docker.errors.APIError as e:
        print('Failed to create network.', file=sys.stderr)
        print(e, file=sys.stderr)
        network = None
    return network

def remove_project_network(cli, network, timeout=0xFFFF):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, docker.models.networks.Network): raise TypeError('Parameter is not valid type.')
    network_info = inspect_project_network(network)
    network.remove()
    removed = False
    for tick in range(timeout):
        if not get_project_networks(cli, network_info['key'].hex):
            removed = True
            break
        else:
            print(f"Wait to remove network [{tick}s]", end="\r")
            time.sleep(1)
    if not removed:
        print(f"Failed to remove network.", file=sys.stderr)
        return False
    return True

# Manage services and tasks
def get_containers(cli, project_key=None, extra_filters={}):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    filters = [f'MLAD.PROJECT={project_key}' if project_key else 'MLAD.PROJECT']
    filters += [f'{key}={value}' for key, value in extra_filters.items()]
    services = cli.containers.list(filters={'label': filters})
    if project_key:
        return dict([(_.attrs['Spec']['Labels']['MLAD.PROJECT.SERVICE'], _) for _ in services])
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

def inspect_service(service):
    if not isinstance(service, docker.models.services.Service): raise TypeError('Parameter is not valid type.')
    labels = service.attrs['Spec']['Labels']
    hostname, path = labels['MLAD.PROJECT.WORKSPACE'].split(':')
    inspect = {
        'key': uuid.UUID(labels['MLAD.PROJECT']),
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': labels['MLAD.PROJECT.USERNAME'],
        'network': labels['MLAD.PROJECT.NETWORK'],
        'project': labels['MLAD.PROJECT.NAME'],
        'id': uuid.UUID(labels['MLAD.PROJECT.ID']),
        'version': labels['MLAD.PROJECT.VERSION'],
        'base': labels['MLAD.PROJECT.BASE'],
        'image': service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'], # Replace from labels['MLAD.PROJECT.IMAGE']

        'name': labels['MLAD.PROJECT.SERVICE'], 
        'replicas': service.attrs['Spec']['Mode']['Replicated']['Replicas'],
        'tasks': dict([(task['ID'], task) for task in service.tasks()]),
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

def get_task_ids(cli, project_key, extra_filters={}):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    filters = f'MLAD.PROJECT={project_key}'
    filters += [f'{key}={value}' for key, value in extra_filters.items()]
    services = cli.services.list(filters={'label': filters})
    return [__['ID'][:SHORT_LEN] for _ in services for __ in _.tasks()]

def create_services(cli, network, services, extra_labels={}):
    from mladcli.default import project_service as service_default
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
        if swarm_mode:
            if get_services(cli, project_info['key'], extra_filters={'MLAD.PROJECT.SERVICE': name}):
                raise exception.Duplicated('Already running service.')
        else:
            if get_containers(cli, project_info['key'], extra_filters={'MLAD.PROJECT.SERVICE': name}):
                raise exception.Duplicated('Already running service.')

        image = service['image'] or image_name
        env = utils.get_service_env()
        env += [f"TF_CPP_MIN_LOG_LEVEL=3"]
        env += [f"PROJECT={project_info['project']}"]
        env += [f"USERNAME={project_info['username']}"]
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
        if swarm_mode:
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
        if not swarm_mode:
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
            instances += instance
        else:
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

def remove_containers(cli, containers, timeout=0xFFFF):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    for _ in names:
        for container in containers:
            print(f"Stop {service.name}...")
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

def prune_images(cli, project_key):
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
 
def get_nodes(cli, node_key=None):
    if not isinstance(cli, docker.client.DockerClient): raise TypeError('Parameter is not valid type.')
    if node_key:
        return cli.nodes.get(node_key)
    else: 
        return dict([(_.short_id, _) for _ in cli.nodes.list()])

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








# for Command Line Interface (Local)
def image_list(project=None):
    cli = get_docker_client()
    project_key = utils.project_key(utils.get_workspace())
    images = get_images(cli, project_key)

    dummies = 0
    data = []
    for image in images:
        if image.tags:
            head = max([ tag.endswith('latest') for tag in image.tags ])
            repository, tag = sorted(image.tags)[0].rsplit(':', 1)
            data.append((
                image.short_id[-SHORT_LEN:], 
                repository,
                tag,
                head,
                image.labels['MLAD.PROJECT.NAME'], 
                image.attrs['Author'], 
                image.attrs['Created'], 
            ))
        else:
            dummies += 1
    return data, dummies

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

def image_remove(ids, force):
    config = utils.read_config()
    cli = get_docker_client()
    try:
        result = remove_image(cli, ids, force)
    except docker.errors.ImageNotFound as e:
        print(e, file=sys.stderr)
        result = []
    return result

def image_prune(project):
    cli = get_docker_client()
    project_key = utils.project_key(utils.get_workspace())
    return prune_images(cli, project_key)

def image_push(project):
    config = utils.read_config()
    cli = get_docker_client()
    try:
        project_key = utils.project_key(utils.get_workspace())
        for _ in push_images(cli, project_key):
            if 'error' in _:
                raise docker.errors.APIError(_['error'], None)
            elif 'stream' in _:
                sys.stdout.write(_['stream'])
    except docker.errors.APIError as e:
        print(e, file=sys.stderr)
        print('Failed to Update Image to Registry.', file=sys.stderr)
        print('Please Check Registry Server.', file=sys.stderr)
        sys.exit(1)
    except StopIteration:
        pass
    
# Project
def running_projects():
    config = utils.read_config()
    cli = get_docker_client()
    data = {}
    for service in get_services(cli).values():
        inspect = inspect_service(service)
        default = { 
            'username': inspect['username'], 
            'project': inspect['name'], 
            'image': inspect['image'],
            'services': 0, 'replicas': 0, 'tasks': 0 
        }
        project_key = inspect['key']
        data[project_key] = data[project_key] if project_key in data else default
        data[project_key]['services'] += 1
        data[project_key]['replicas'] += inspect['replicas']
        data[project_key]['tasks'] += [_['Status']['State'] for _ in inspect['tasks'].values()].count('running')
    return data

def images_up(project, services, by_service=False):
    config = utils.read_config()

    cli = get_docker_client()
    base_labels = make_base_labels(utils.get_workspace(), config['account']['username'], project)
    project_key = base_labels['MLAD.PROJECT']
    
    # Get Network
    if not project['partial']:
        try:
            network = create_project_network(cli, base_labels, swarm=by_service)
        except exception.AlreadyExist as e:
            print(e, file=sys.stderr)
            print('Already running project.', file=sys.stderr)
            sys.exit(1)
    else:
        network = create_project_network(cli, base_labels, swarm=by_service, allow_reuse=True)

    network_inspect = inspect_project_network(network)
    project_version = network_inspect['version']

    # Check service status
    running_services = get_services(cli, project_key)
    for service_name in services:
        if service_name in running_services:
            print(f'Already running service[{service_name}] in project.', file=sys.stderr)
            sys.exit(1)

    project_info = inspect_project_network(network)
    with InterruptHandler(message='Wait.', blocked=True) as h:
        instances = create_services(cli, network, services)  
        for instance in instances:
            print(f'Start {instance}...', end=' ')
            time.sleep(1)
        if h.interrupted:
            return None
    return project_info['base']
            
def show_logs(project, tail='all', follow=False, timestamps=False, filters=[], by_service=False):
    project_key = utils.project_key(utils.get_workspace())
    project_version=project['version'].lower()
    config = utils.read_config()

    def query_logs(target, **params):
        if config['docker']['host'].startswith('http://') or config['docker']['host'].startswith('https://'):
            host = config['docker']['host'] 
        elif config['docker']['host'].startswith('unix://'):
            host = f"http+{config['docker']['host'][:7]+config['docker']['host'][7:].replace('/', '%2F')}"
        else:
            host = f"http://{config['docker']['host']}"

        import requests_unixsocket
        with requests_unixsocket.get(f"{host}/v1.24{target}/logs", params=params, stream=True) as resp:
            for line in resp.iter_lines():
                out = line[docker.constants.STREAM_HEADER_SIZE_BYTES:].decode('utf8')
                if timestamps:
                    temp = out.split(' ')
                    out = ' '.join([temp[1], temp[0]] + temp[2:])
                yield out.encode('utf8')
        return ''

    cli = get_docker_client()
    with InterruptHandler() as h:
        if by_service:
            instances = cli.services.list(filters={'label': f'MLAD.PROJECT={project_key}'})
            filtered = []
            services = [(inst.attrs['Spec']['Labels']['MLAD.PROJECT.SERVICE'], f"/services/{inst.attrs['ID']}", inst.tasks()) for inst in instances]
            if filters:
                for _ in services:
                    if _[0] in filters:
                        filtered.append(_[:2])
                    else:
                        filtered += [(_[0], f"/tasks/{task['ID']}") for task in _[2] if task['ID'][:SHORT_LEN] in filters]
            else:
                filtered = [_[:2] for _ in services]
            logs = [ (service_name, query_logs(target, details=True, follow=follow, tail=tail, timestamps=timestamps, stdout=True, stderr=True)) for service_name, target in filtered ]
        else:
            instances = cli.containers.list(all=True, filters={'label': f'MLAD.PROJECT={project_key}'})
            timestamps = True
            logs = [ (inst.attrs['Config']['Labels']['MLAD.PROJECT.SERVICE'], inst.logs(follow=follow, tail=tail, timestamps=timestamps, stream=True)) for inst in instances ]

        if len(logs):
            name_width = min(32, max([len(name) for name, _ in logs]))
            loggers = [ LoggerThread(name, name_width, log, by_service, timestamps, SHORT_LEN) for name, log in logs ]
            for logger in loggers: logger.start()
            while not h.interrupted and max([ not logger.interrupted for logger in loggers ]):
                time.sleep(0.01)
            for logger in loggers: logger.interrupt()
        else:
            print('Cannot find running project.', file=sys.stderr)

def images_down(project, services, by_service=False):
    config = utils.read_config()
    project_key = utils.project_key(utils.get_workspace())

    cli = get_docker_client()

    # Block duplicated running.
    network = get_project_networks(cli, project_key)
    if not project['partial']:
        if not network:
            print('Already stopped project.', file=sys.stderr)
            sys.exit(1)
    else:
        running_services = get_services(cli, project_key)
        for service_name in services:
            if not service_name in running_services:
                print(f'Already stopped service[{service_name}] in project.', file=sys.stderr)
                sys.exit(1)
    inspect = inspect_project_network(network)
    project_id = inspect['id']

    with InterruptHandler(message='Wait.', blocked=True):
        if by_service:
            running_services = get_services(cli, project_key).values()
            targets = [_ for _ in running_services if inspect_service(_)['name'] in services]
            remove_services(cli, targets)
        else:
            running_containers = get_containers(cli, project_key).values()
            targets = [_ for _ in running_containers if inspect_service(_)['name'] in services]
            remove_containers(cli, targets)
        if not project['partial']:
            try:
                remove_project_network(cli, network)
                print('Network removed.')
            except docker.errors.APIError as e:
                print('Network already removed.', file=sys.stderr)

def show_status(project, services, all=False):
    project_key = utils.project_key(utils.get_workspace())
    cli = get_docker_client()

    # Block not running.
    network = get_project_networks(cli, project_key)
    if not network:
        print('Cannot find running service.', file=sys.stderr)
        sys.exit(1)

    task_info = []
    for service_name, service in get_services(cli, project_key).items():
        inspect = inspect_service(service)
        try:
            for task_id, task in inspect['tasks'].items():
                uptime = (datetime.utcnow() - parser.parse(task['Status']['Timestamp']).replace(tzinfo=None)).total_seconds()
                if uptime > 24 * 60 * 60:
                    uptime = f"{uptime // (24 * 60 * 60):.0f} days"
                elif uptime > 60 * 60:
                    uptime = f"{uptime // (60 * 60):.0f} hours"
                elif uptime > 60:
                    uptime = f"{uptime // 60:.0f} minutes"
                else:
                    uptime = f"{uptime:.0f} seconds"
                if all or task['Status']['State'] not in ['shutdown', 'failed']:
                    task_info.append((
                        task_id,
                        service_name,
                        task['Slot'],
                        inspect_node(get_nodes(cli, task['NodeID']))['hostname'] if 'NodeID' in task else '-',
                        task['DesiredState'].title(), 
                        f"{task['Status']['State'].title()}", 
                        uptime,
                        ', '.join([_ for _ in inspect['ports']]),
                        task['Status']['Err'] if 'Err' in task['Status'] else '-'
                    ))
        except docker.errors.NotFound as e:
            pass
    return task_info
    
def scale_service(project, scale_spec):
    project_key = utils.project_key(utils.get_workspace())
    
    cli = get_docker_client()
    
    # Block not running.
    network = get_project_networks(cli, project_key)
    if not network:
        print('Cannot find running service.', file=sys.stderr)
        sys.exit(1)

    # Inspect Data
    inspect = inspect_project_network(network)

    for service_name in scale_spec:
        try:
            services = get_services(cli, project_key, extra_filters={'MLAD.PROJECT.SERVICE': service_name})
            for service in services:
                if service.scale(int(scale_spec[service_name])):
                    print(f'Change scale service [{service_name}].')
                else:
                    print(f'Failed to change scale service [{service_name}].')
        except docker.errors.NotFound:
            print(f'Cannot find service [{service_name}].', file=sys.stderr)

def get_running_services(project):
    project_key = utils.project_key(utils.get_workspace())
    cli = get_docker_client()
    services = get_services(cli, project_key)
    #print( [name for name, service in services if inspect_service(service)[''] ==  ) 
    print (services.items())

def node_list():
    cli = get_docker_client()
    return [inspect_node(_) for _ in get_nodes(cli).values()]

def node_enable(node_key):
    cli = get_docker_client()
    return enable_node(cli, node_key)

def node_disable(node_key):
    cli = get_docker_client()
    return disable_node(cli, node_key)

def node_label_add(node_key, **kvs):
    cli = get_docker_client()
    return add_node_labels(cli, node_key, **kvs)

def node_label_rm(node_key, *keys):
    cli = get_docker_client()
    return remove_node_labels(cli, node_key, *keys)
