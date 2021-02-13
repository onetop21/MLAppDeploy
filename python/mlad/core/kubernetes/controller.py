import sys
import copy
import time
import json
import uuid
import base64
from pathlib import Path
from typing import Dict, List
import docker
from kubernetes.client import models
import requests
from mlad.core import exception
from mlad.core.libs import utils
#from mlad.core.docker.logs import LogHandler, LogCollector
from mlad.core.default import project_service as service_default
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from mlad.core.docker import controller as docker_controller

# https://github.com/kubernetes-client/python/blob/release-11.0/kubernetes/docs/CoreV1Api.md

SHORT_LEN = 10

# Docker CLI from HOST
def get_api_client(config_file=config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION):
    #from kubernetes.client.api_client import ApiClient
    #config.load_kube_config(config_file=config_file) # configuration to Configuration(global)
    #return ApiClient() # If Need, set configuration parameter from client.Configuration
    return config.new_client_from_config(config_file=config_file)

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
    return docker_controller.get_auth_headers(docker.from_env(), image_name, auth_configs)

def get_project_networks(cli):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    namespaces = api.list_namespace(label_selector="MLAD.PROJECT")
    return dict([(_.metadata.name, _) for _ in namespaces.items])

def get_project_network(cli, **kwargs):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    if kwargs.get('project_key'):
        namespaces = api.list_namespace(label_selector=f"MLAD.PROJECT={kwargs.get('project_key')}")
    elif kwargs.get('project_id'):
        namespaces = api.list_namespace(label_selector=f"MLAD.PROJECT.ID={kwargs.get('project_id')}")
    elif kwargs.get('network_id'):
        all_namespaces = api.list_namespace(label_selector="MLAD.PROJECT")
        namespaces = list(filter(lambda _: _.metadata.uid==kwargs.get('network_id'), all_namespaces))
    else:
        raise TypeError('At least one parameter is required.')
    if len(namespaces) == 1:
        return namespaces[0]
    elif len(namespaces) == 0:
        return None
    else:
        raise exception.Duplicated(f"Need to remove networks or down project, because exists duplicated networks.")

def get_labels(obj):
    if isinstance(obj, client.models.v1_namespace.V1Namespace):
        return obj.metadata.labels
    elif isinstance(obj, client.models.v1_replication_controller.V1ReplicationController):
        return obj.metadata.labels
    elif isinstance(obj, client.models.v1_service.V1Service):
        return obj.metadata.labels
    else:
        raise TypeError('Parameter is not valid type.')

def inspect_project_network(network):
    if not isinstance(network, client.models.v1_namespace.V1Namespace): raise TypeError('Parameter is not valid type.')
    labels = get_labels(network)
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

def create_project_network(cli, base_labels, extra_envs, swarm=True, allow_reuse=False, stream=False):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    #workspace = utils.get_workspace()
    project_key = base_labels['MLAD.PROJECT']
    network = get_project_network(cli, project_key=project_key)
    if network:
        if allow_reuse:
            if stream:
                def resp_stream():
                    yield {'result': 'exists', 'name': network.metadata.name, 'id': network.metadata.uid}
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
        network_name = f"{basename}-cluster"
        try:
            message = f"Create project network [{network_name}]...\n"
            yield {'stream': message}
            labels = copy.deepcopy(base_labels)
            labels.update({
                'MLAD.PROJECT.NETWORK': network_name, 
                'MLAD.PROJECT.ID': str(utils.generate_unique_id()),
                'MLAD.PROJECT.AUTH_CONFIGS': get_auth_headers(cli)['X-Registry-Config'].decode(),
                'MLAD.PROJECT.ENV': utils.encode_dict(extra_envs),
            })

            ret = api.create_namespace(
                client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        name=network_name, 
                        labels=labels
                    )
                )
            )
        except ApiException as e:
            message = f"Failed to create network.\n{e}\n"
            yield {'result': 'failed', 'stream': message}
    if stream:
        return resp_stream()
    else:
        stream_out = (_ for _ in resp_stream())
        return (get_project_network(cli, project_key=project_key), stream_out)

def remove_project_network(cli, network, timeout=0xFFFF, stream=False):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, client.models.v1_namespace.V1Namespace): raise TypeError('Parameter is not valid type.')
    network_info = inspect_project_network(network)
    cli.delete_namespace(network.metadata.name)
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
    return docker_controller.get_containers(docker.from_env(), project_key, extra_filters)

def get_services(cli, project_key=None, extra_filters={}):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    filters = [f'MLAD.PROJECT={project_key}' if project_key else 'MLAD.PROJECT']
    filters += [f'{key}={value}' for key, value in extra_filters.items()]
    services = cli.list_service_for_all_namespaces(label_selector=','.join(filters))
    if project_key:
        return dict([(_.metadata.labels['MLAD.PROJECT.SERVICE'], _) for _ in services])
    else:
        return dict([(_.name, _) for _ in services])

def get_service(cli, service_id):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    services = cli.list_service_for_all_namespaces(label_selector='MLAD.PROJECT')
    return dict([(_.metadata.uid, _) for _ in services]).get(service_id)

def inspect_container(container):
    return docker_controller.inspect_container(container)

def inspect_service(service):
    if not isinstance(service, client.models.v1_service.V1Service): raise TypeError('Parameter is not valid type.')
    labels = service.metadata.labels
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
    return docker_controller.create_containers(docker.from_env(), network, services, extra_labels)

def create_services(cli, network, services, extra_labels={}):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, client.models.v1_namespace.V1Namespace): raise TypeError('Parameter is not valid type.')
    project_info = inspect_project_network(network)
    network_labels = get_labels(network)
    
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

        try:
            ret = v1.create_namespaced_replication_controller(
                namespace=namespace,
                body=client.V1ReplicationController(
                    metadata=client.V1ObjectMeta(
                        name=name,
                        labels=kwargs.get('labels', {})
                    ),
                    spec=client.V1ReplicationControllerSpec(
                        replicas=kwargs.get('replicas', 1),
                        selector={'MLAD.PROJECT.SERVICE': name},
                        template=client.V1PodTemplateSpec(
                            metadata=client.V1ObjectMeta(
                                name=name,
                                labels=kwargs.get('labels', {})
                            ),
                            spec=client.V1PodSpec(
                                containers=[client.V1Container(
                                    name=name,
                                    image=kwargs.get('image', labels['MLAD.PROJECT.IMAGE']),
                                    env=env,
                                    #restart_policy,
                                    #resources;
                                    #mode
                                    #constraints
                                    command=kwargs.get('command', [])
                                )]
                            )
                        )
                    )
                )
            )
            ret = v1.create_namespaced_service(namespace, client.V1Service(
                metadata=client.V1ObjectMeta(
                    name=name,
                ),
                spec=client.V1ServiceSpec(
                    selector={'MLAD.PROJECT.SERVICE': name},
                    ports=[client.V1ServicePort(port=_) for _ in kwargs.get('ports', [])]
                )
            ))
        except ApiException as e:
            print(f"Exception Handling v1.create_namespaced_replication_controller => {e}", file=sys.stderr)
    return ret

def remove_containers(cli, containers):
    return docker_controller.remove_containers(docker.from_env(), containers)

def remove_services(cli, services, timeout=0xFFFF):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    
    for service in services:
        inspect = inspect_service(service)
        print(f"Stop {inspect['name']}...")
        ret = v1.delete_namespaced_service(inspect['name'], namespace)
        ret = v1.delete_namespaced_replication_controller(inspect['name'], namespace, propagation_policy='Foreground')
    removed = True
    for service in services:
        service_removed = False
        for _ in range(timeout):
            try:
                #service.reload()
                pass
            except docker.errors.NotFound:
                service_removed = True
                break
            time.sleep(1)
        removed &= service_removed
    return removed

# Image Control
def get_images(cli, project_key=None):
    return docker_controller.get_images(docker.from_env(), project_key)

def get_image(cli, image_id):
    return docker_controller.get_image(docker.from_env(), image_id)

def inspect_image(image):
    return docker_controller.inspect_image(image)

def build_image(cli, base_labels, tar, dockerfile, stream=False):
    return docker_controller.build_image(docker.from_env(), base_labels, tar, dockerfile, stream)

def remove_image(cli, ids, force=False):
    return docker_controller.remove_image(docker.from_env(), ids, force)

def prune_images(cli, project_key=None):
    return docker_controller.prune_images(docker.from_env(), project_key)

def push_images(cli, project_key, stream=False):
    return docker_controller.push_images(docker.from_env(), project_key, stream)
 
def get_nodes(cli):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    print([(_.metadata.name, _.metadata) for _ in api.list_node().items])
    return dict(
        [(_.metadata.name, _.metadata) for _ in api.list_node().items]
    )

def get_node(cli, node_key):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    nodes = api.list_node(field_selector=f"metadata.name={node_key}")
    if not nodes.items:
        nodes = api.list_node(field_selector=f"metadata.uid={node_key}")
    if nodes.items: 
        return nodes.items[0]
    else:
        #print(f'Cannot find node "{node_key}"', file=sys.stderr)
        raise exception.NotFound(f'Cannot find node "{node_key}"')

def inspect_node(node):
    if not isinstance(node, client.models.v1_node.V1Node): raise TypeError('Parameter is not valid type.')
    hostname = node.metadata.labels['kubernetes.io/hostname']
    availability = node.spec.taints != None
    platform = node.metadata.labels['kubernetes.io/os']    
    resources = node.status.capacity
    engine_version = node.status.node_info.kubelet_version
    role = [_.split('/')[-1] for _ in node.metadata.labels if _.startswith('node-role')][-1]
    status = '-'
    return {
        'id': node.metadata.uid,
        'hostname': hostname,#node.metadata.name,
        'labels': node.metadata.labels,
        'role': role,
        'availability': availability,
        'platform': platform,
        'resources': resources,
        'engine_version': engine_version,
        'status': status,
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



if __name__ == '__main__':
    cli = get_api_client()
    api_instance = client.CoreV1Api(cli)
    ret = api_instance.list_node()
    print(ret.items[-1], type(ret.items[-1]))
    sys.exit(1)

    # print(type(v1)) == kubernetes.client.api.core_v1_api.CoreV1Api
    v1 = client.CoreV1Api(cli)
    body = client.V1Namespace(metadata=client.V1ObjectMeta(name="hello-cluster", labels={'MLAD.PROJECT': '123', 'MLAD.PROJECT.NAME':'hello'}))
    try:
        ret = v1.create_namespace(body)
        print(ret)
    except ApiException as e:
        print(f"Exception Handling v1.create_namespace => {e}", file=sys.stderr)
    ret = v1.list_namespace(label_selector="MLAD.PROJECT=123", watch=False)
    print('Project Networks', [_.metadata.name for _ in ret.items])
    namespace = [_.metadata.name for _ in ret.items][-1]

    #if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    #if not isinstance(network, client.models.v1_namespace.V1Namespace): raise TypeError('Parameter is not valid type.')
    
    def create_service(name, *args):
        cli = get_api_client()
        print(get_project_networks(cli))
        print(type(get_project_networks(cli)['hello-cluster']))
        #sys.exit(1)
        body = client.V1ReplicationController()
        body.metadata = client.V1ObjectMeta()
        body.metadata.name = name
        body.metadata.labels = {'MLAD.PROJECT': '123', 'MLAD.PROJECt.SERVICE': body.metadata.name}
        body.spec = client.V1ReplicationControllerSpec()
        body.spec.replicas = 1
        body.spec.selector = {'app': body.metadata.name}
        body.spec.template = client.V1PodTemplateSpec()
        body.spec.template.metadata = client.V1ObjectMeta()
        body.spec.template.metadata.name = body.metadata.name
        body.spec.template.metadata.labels = {'app': body.metadata.name}
        container = client.V1Container(name=body.metadata.name)
        container.image = 'onetop21/example-029f0590f6:latest'
        container.image_pull_policy="IfNotPresent"
        container.args=[*args]
        container.restart_policy='Never'
        body.spec.template.spec = client.V1PodSpec(containers=[container], hostname=body.metadata.name, subdomain='hello')
        try:
            ret = v1.create_namespaced_replication_controller(namespace, body)
            ret = v1.create_namespaced_service(namespace, client.V1Service(
                metadata=client.V1ObjectMeta(
                    name=body.metadata.name,
                ),
                spec=client.V1ServiceSpec(
                    selector={'app': body.metadata.name},
                    ports=[client.V1ServicePort(port=5555)]
                )
            ))
        except ApiException as e:
            print(f"Exception Handling v1.create_namespaced_replication_controller => {e}", file=sys.stderr)
            ret = v1.delete_namespaced_replication_controller(body.metadata.name, namespace, propagation_policy='Foreground')
            ret = v1.delete_namespaced_service(body.metadata.name, namespace)
        
        return ret
    create_service("server", 'python', 'server.py')
    create_service("client", 'python', 'client.py')
    print(ret)


