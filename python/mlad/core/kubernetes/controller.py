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
from mlad.core.kubernetes.logs import LogHandler, LogCollector
from mlad.core.default import project_service as service_default
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException
from mlad.core.docker import controller as docker_controller

# https://github.com/kubernetes-client/python/blob/release-11.0/kubernetes/docs/CoreV1Api.md

SHORT_LEN = 10

# Docker CLI from HOST
def get_api_client(config_file='~/.kube/config'):#config.kube_config.KUBE_CONFIG_DEFAULT_LOCATION):
    try:
        #from kubernetes.client.api_client import ApiClient
        #config.load_kube_config(config_file=config_file) # configuration to Configuration(global)
        #return ApiClient() # If Need, set configuration parameter from client.Configuration
        return config.new_client_from_config(config_file=config_file)
    except config.config_exception.ConfigException:
        from kubernetes.client.api_client import ApiClient
        config.load_incluster_config() # configuration to Configuration(global)
        return ApiClient() # If Need, set configuration parameter from client.Configuration

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
    if not namespaces.items:
        return None
    elif len(namespaces.items)==1:
        return namespaces.items[0]
    else:
        raise exception.Duplicated(f"Need to remove networks or down project, because exists duplicated networks.")

def get_labels(obj):
    #TODO to be modified
    if isinstance(obj, client.models.v1_namespace.V1Namespace):
        return obj.metadata.labels
    elif isinstance(obj, client.models.v1_replication_controller.V1ReplicationController):
        return obj.metadata.labels
    elif isinstance(obj, client.models.v1_service.V1Service):
        return obj.metadata.labels
    else:
        raise TypeError('Parameter is not valid type.')

def get_config_labels(cli, obj, key):
    #key='base_labels', 'service_labels'
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    if isinstance(obj,client.models.v1_namespace.V1Namespace):
        namespace = obj.metadata.name
    elif isinstance(obj, client.models.v1_service.V1Service):
        namespace = obj.metadata.namespace
    ret = api.read_namespaced_config_map(key, namespace)
    return ret.data

def create_config_labels(cli, key, namespace, labels):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    ret = api.create_namespaced_config_map(
        namespace, 
        client.V1ConfigMap(
            data=labels,
            metadata=client.V1ObjectMeta(name=key)
        )
    )
    return ret.data

def inspect_project_network(cli, network):
    if not isinstance(network, client.models.v1_namespace.V1Namespace): raise TypeError('Parameter is not valid type.')
    labels = get_labels(network) #labels from namespace
    config_labels = get_config_labels(cli, network, 'project-labels')
    hostname, path = config_labels['MLAD.PROJECT.WORKSPACE'].split(':')
    return {
        'key': uuid.UUID(labels['MLAD.PROJECT']),
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': config_labels['MLAD.PROJECT.USERNAME'],
        'name': config_labels['MLAD.PROJECT.NETWORK'],
        'project': labels['MLAD.PROJECT.NAME'],
        'id': uuid.UUID(config_labels['MLAD.PROJECT.ID']),
        'version': config_labels['MLAD.PROJECT.VERSION'],
        'base': config_labels['MLAD.PROJECT.BASE'],
        'image': config_labels['MLAD.PROJECT.IMAGE'],
    }

def create_project_network(cli, base_labels, extra_envs, credential, swarm=True, allow_reuse=False, stream=False):
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
                'MLAD.PROJECT.ENV': utils.encode_dict(extra_envs),
            })
            keys = {
                'MLAD.PROJECT':labels['MLAD.PROJECT'],
                'MLAD.PROJECT.NAME':labels['MLAD.PROJECT.NAME'],
            }
            ret = api.create_namespace(
                client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        name=network_name, 
                        labels=keys
                    )
                )
            )
            config_map_ret=create_config_labels(cli, 'project-labels', 
                network_name, labels)
            #AuthConfig
            api.create_namespaced_secret(network_name,
                client.V1Secret(
                    metadata=client.V1ObjectMeta(
                       name=f"{basename}-auth"
                    ),
                    type='kubernetes.io/dockerconfigjson',
                    data={'.dockerconfigjson': credential}
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
    api = client.CoreV1Api(cli)
    network_info = inspect_project_network(cli, network)
    ret = api.delete_namespace(network.metadata.name)
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
    api = client.CoreV1Api(cli)
    filters = [f'MLAD.PROJECT={project_key}' if project_key else 'MLAD.PROJECT']
    filters += [f'{key}={value}' for key, value in extra_filters.items()]
    services = api.list_service_for_all_namespaces(label_selector=','.join(filters))
    if project_key:
        return dict([(_.metadata.labels['MLAD.PROJECT.SERVICE'], _) for _ in services.items])
    else:
        return dict([(_.metadata.name, _) for _ in services.items])

def get_service(cli, service_id):
    #service_id = k8s service uid
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    service = api.list_service_for_all_namespaces(label_selector=f"uid={service_id}")
    return service.items[0]

def inspect_container(container):
    return docker_controller.inspect_container(container)

def get_pod_info(pod):
    if not isinstance(pod, client.models.v1_pod.V1Pod): raise TypeError('Parameter is not valid type.')
         
    pod_info = {
        'name': pod.metadata.name, #pod name
        'namespace': pod.metadata.namespace,
        'created': pod.metadata.creation_timestamp,
        'container_status': list(),
        'status': dict(),  
        'node': pod.spec.node_name,
        'phase': pod.status.phase
    }
    def get_status(container_state):
        if container_state.running:
            return {'state':'Running', 'detail':None}
        if container_state.terminated:
            return {
                'state':'Terminated', 
                'detail':{
                    'reason':container_state.terminated.reason,
                    'finished': container_state.terminated.finished_at}
                }
        if container_state.waiting:
            return {
                'state':'Waiting', 
                'detail':{
                    'reason':container_state.waiting.reason}
                }
    
    def parse_status(containers):
        status = {'state':'Running', 'detail':None}
        # if not running container exits, return that
        completed = 0
        for _ in containers:
            if _['status']['state'] == 'Waiting':
                return _['status']
            elif _['status']['state'] == 'Terminated':
                if _['status']['detail']['reason'] == 'Completed':
                    completed +=1
                    if completed == len(containers):
                        return _['status']
                    else:
                        pass
                else:
                    return _['status']
        return status

    for container in pod.status.container_statuses:
        container_info = {
            'container_id': container.container_id,
            'restart': container.restart_count,
            'status': get_status(container.state),
            'ready': container.ready
        }
        pod_info['container_status'].append(container_info)
    pod_info['status']=parse_status(pod_info['container_status'])
    return pod_info

def _get_job(cli, name, namespace):
    api = client.BatchV1Api(cli)
    return api.read_namespaced_job(name, namespace)

def _get_replication_controller(cli, name, namespace):
    api = client.CoreV1Api(cli)
    return api.read_namespaced_replication_controller(name, namespace)

def inspect_service(cli, service):
    if not isinstance(service, client.models.v1_service.V1Service): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    service_name = service.metadata.name
    namespace = service.metadata.namespace
    config_labels = get_config_labels(cli, service, 
        f'service-{service_name}-labels')
    labels = service.metadata.labels

    type = config_labels['MLAD.PROJECT.SERVICE.TYPE']
    if type == 'job':
        replica_ret = _get_job(cli, service_name, namespace)
    else:
        replica_ret = _get_replication_controller(cli, service_name, namespace)
    pod_ret = api.list_namespaced_pod(namespace, label_selector=f'MLAD.PROJECT.SERVICE={service_name}')

    hostname, path = config_labels.get('MLAD.PROJECT.WORKSPACE', ':').split(':')
   
    inspect = {
        'key': uuid.UUID(config_labels['MLAD.PROJECT']) if config_labels.get('MLAD.VERSION') else '',
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': config_labels.get('MLAD.PROJECT.USERNAME'),
        'network': config_labels.get('MLAD.PROJECT.NETWORK'),
        'project': config_labels.get('MLAD.PROJECT.NAME'),
        'project_id': uuid.UUID(config_labels['MLAD.PROJECT.ID']) if config_labels.get('MLAD.VERSION') else '',
        'version': config_labels.get('MLAD.PROJECT.VERSION'),
        'base': config_labels.get('MLAD.PROJECT.BASE'),
        'image': replica_ret.spec.template.spec.containers[0].image, # Replace from labels['MLAD.PROJECT.IMAGE']

        'id': service.metadata.uid,
        'name': config_labels.get('MLAD.PROJECT.SERVICE'), 
        'replicas': replica_ret.spec.replicas if type == 'rc' else 0,
        'tasks': dict([(pod.metadata.name, get_pod_info(pod)) for pod in pod_ret.items]),
        'ports': {}
    }
    #TODO SERVICE PORTS
    if service.spec.ports:
        for _ in service.spec.ports:
            target = _.target_port
            published = _.port
            inspect['ports'][f"{target}->{published}"] = {
                'target': target,
                'published': published
            }
    return inspect

def create_containers(cli, network, services, extra_labels={}):
    return docker_controller.create_containers(docker.from_env(), network, services, extra_labels)

def _create_job(cli, name, image, command, namespace='default', envs=None, 
                restart_policy='Never', cpu='1', gpu='0', mem=None, 
                labels=None, constraints=None):
    api = client.BatchV1Api(cli)
    body=client.V1Job(
        metadata=client.V1ObjectMeta(name=name,labels=labels),
        spec=client.V1JobSpec(
            backoff_limit=6,
            selector={'MLAD.PROJECT.SERVICE': name},
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(name=name, labels=labels),
                spec=client.V1PodSpec(
                    restart_policy=restart_policy,
                    #termination_grace_period_seconds=30,
                    containers=[
                        client.V1Container(
                            name=name,
                            image=image,
                            #image_pull_policy='Always',
                            command=command,
                            env=envs,
                            resources=client.V1ResourceRequirements(
                                limits={
                                    'cpu': cpu,
                                    'nvidia.com/gpu': gpu,
                                    'memory': mem if mem else '512Mi'
                                },
                                requests={
                                    'cpu': cpu,
                                    'nvidia.com/gpu': gpu,
                                    'memory': mem if mem else '256Mi'
                                }
                            )
                        )
                    ],
                    node_selector = constraints
                )
            )
        )  
    )
    api_response = api.create_namespaced_job(namespace, body)
    return api_response

def _create_replication_controller(cli, name, image, command, namespace='default',
                                   envs=None, restart_policy='Always', 
                                   replicas=1, cpu='1', gpu='0', mem=None,
                                   labels=None, constraints=None):
    api = client.CoreV1Api(cli)
    body=client.V1ReplicationController(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=labels
        ),
        spec=client.V1ReplicationControllerSpec(
            replicas=replicas,
            selector={'MLAD.PROJECT.SERVICE': name},
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels
                ),
                spec=client.V1PodSpec(
                    restart_policy=restart_policy, #Always, OnFailure, Never
                    containers=[client.V1Container(
                        name=name,
                        image=image,
                        env=envs,
                        command=command,
                        resources=client.V1ResourceRequirements(
                            limits={
                                'cpu': cpu,
                                'nvidia.com/gpu': gpu,
                                'memory': mem if mem else '512Mi'
                            },
                            requests={
                                'cpu': cpu,
                                'nvidia.com/gpu': gpu,
                                'memory': mem if mem else '256Mi'
                            }
                        )
                    )],
                    node_selector = constraints
                )
            )
        )
    )    
    api_response = api.create_namespaced_replication_controller(namespace, body)
    return api_response

def create_services(cli, network, services, extra_labels={}):
    #type = 'job'
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    if not isinstance(network, client.models.v1_namespace.V1Namespace): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    namespace = network.metadata.name
    project_info = inspect_project_network(cli, network)
    config_labels = get_config_labels(cli, network, 'project-labels')
    network_labels = get_labels(network)
    # Update Project Name
    #project_info = inspect_project_network(network)
    image_name = project_info['image']
    project_base = project_info['base']
    
    instances = []
    for name in services:
        service = service_default(services[name])

        # Check running already
        if get_services(cli, project_info['key'], extra_filters={'MLAD.PROJECT.SERVICE': name}):
            raise exception.Duplicated('Already running service.')

        image = service['image'] or image_name
        env = utils.decode_dict(config_labels['MLAD.PROJECT.ENV'])
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
        
        restart_policy = service['deploy']['restart_policy']['condition']
        type = service['type']
        constraints = service['deploy']['constraints']

        # Resource Spec
        resources = service['deploy']['quota']
        cpu = resources['cpus'] if 'cpus' in resources else 1
        gpu = resources['gpus'] if 'gpus' in resources else 0
        mem = resources['gpus'] if 'mems' in resources else None

        # if 'mems' in service['deploy']['quota']: 
        #     data = str(service['deploy']['quota']['mems'])
        #     size = int(data[:-1])
        #     unit = data.lower()[-1:]
        #     if unit == 'g':
        #         size *= (2**30)
        #     elif unit == 'm':
        #         size *= (2**20)
        #     elif unit == 'k':
        #         size *= (2**10)
        #     res_spec['mem_limit'] = size
        #     res_spec['mem_reservation'] = size

        ports = service['deploy']['ports']
        
        # Try to run
        inst_name = f"{project_base}-{name}"
        kwargs = {
            'name': inst_name,
            #hostname=f'{name}.{{{{.Task.Slot}}}}',
            'image': image, 
            'env': env + ['TASK_ID={{.Task.ID}}', f'TASK_NAME={name}.{{{{.Task.Slot}}}}', 'NODE_HOSTNAME={{.Node.Hostname}}'],
            'mounts': ['/etc/timezone:/etc/timezone:ro', '/etc/localtime:/etc/localtime:ro'],
            'command': command.split(),
            'container_labels': labels,
            'labels': labels,
            'networks': [{'Target': namespace, 'Aliases': [name]}],
            'restart_policy': restart_policy,
            'constraints': constraints,
            'ports': ports
        }
        #instance = cli.services.create(**kwargs)

        ## Create Service by REST API (with AuthConfig)
        #params = 
        
        #auth_configs = utils.decode_dict(config_labels['MLAD.PROJECT.AUTH_CONFIGS'])
        #headers = get_auth_headers(cli, image, auth_configs) if auth_configs else get_auth_headers(cli, image)
        
        #headers['Content-Type'] = 'application/json'
        #body = utils.change_key_style(docker.models.services._get_create_service_kwargs('create', kwargs))
        #temp_image = kwargs.get('image') if kwargs.get('image') else config_labels['MLAD.PROJECT.IMAGE']
        envs = [client.V1EnvVar(name=_.split('=')[0], value=_.split('=')[1])
               for _ in env]
        command = kwargs.get('command', [])
        replicas = kwargs.get('replicas', 1)
        labels = kwargs.get('labels', {})

        config_labels['MLAD.PROJECT.SERVICE']=name
        config_labels['MLAD.PROJECT.SERVICE.TYPE']=type

        try:
            if type == 'job':
                restart_policy = kwargs.get(restart_policy, 'Never')
                ret = _create_job(cli, name, image, command, 
                            namespace, envs, restart_policy, cpu, gpu, mem, 
                            labels, constraints)
            elif type == 'rc':
                restart_policy = kwargs.get(restart_policy, 'Always')
                ret = _create_replication_controller(
                    cli, name, image, command, 
                    namespace, envs, restart_policy, replicas,
                    cpu, gpu, mem, labels, constraints)
            
            ret = api.create_namespaced_service(namespace, client.V1Service(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels
                ),
                spec=client.V1ServiceSpec(
                    selector={'MLAD.PROJECT.SERVICE': name},
                    ports=[client.V1ServicePort(port=_) for _ in kwargs.get('ports', [])]
                )
            ))
            label_body = {
                "metadata": {
                    "labels": {'uid':ret.metadata.uid}
                    }
            }
            temp_ret  = api.patch_namespaced_service(name,namespace,label_body)
            instances.append(temp_ret)
            ret = create_config_labels(cli, f'service-{name}-labels', namespace, config_labels)
        except ApiException as e:
            print(f"Exception Handling v1.create_namespaced_replication_controller => {e}", file=sys.stderr)
    ret = create_config_labels(cli, 'service-labels', namespace, config_labels)
    return instances

def remove_containers(cli, containers):
    return docker_controller.remove_containers(docker.from_env(), containers)

def _delete_job(cli, name, namespace):
    api = client.BatchV1Api(cli)
    return api.delete_namespaced_job(name, namespace)

def _delete_replication_controller(cli, name, namespace):
    api = client.CoreV1Api(cli)
    return api.delete_namespaced_replication_controller(name, 
        namespace, propagation_policy='Foreground')

def remove_services(cli, services, timeout=0xFFFF):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    for service in services:
        inspect = inspect_service(cli, service)
        service_name = inspect['name']
        namespace = service.metadata.namespace

        config_labels = get_config_labels(cli, service, 
            f'service-{service_name}-labels')
        type = config_labels['MLAD.PROJECT.SERVICE.TYPE'] 

        print(f"Stop {service_name}...")
        ret = api.delete_namespaced_service(service_name, namespace)
        if type == 'job':
            ret = _delete_job(cli, service_name, namespace)
        else:
            ret = _delete_replication_controller(cli, service_name, namespace)
    removed = True
    # for service in services:
    #     service_removed = False
    #     for _ in range(timeout):
    #         try:
    #             #service.reload()
    #             pass
    #         except docker.errors.NotFound:
    #             service_removed = True
    #             break
    #         time.sleep(1)
    #     removed &= service_removed
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
    state = node.status.conditions[-1].type
    addr = node.status.addresses[0].address
    
    return {
        'id': node.metadata.uid,
        'hostname': hostname,#node.metadata.name,
        'labels': node.metadata.labels,
        'role': role,
        'availability': availability,
        'platform': platform,
        'resources': resources,
        'engine_version': engine_version,
        'status': {'State': state, 'Addr':addr},
    }

def enable_node(cli, node_key):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    body = {
        "spec": {"taints": None}
    }
    try:
        api_response = api.patch_node(node_key, body)
    except ApiException as e:
        print(e)
    
def disable_node(cli, node_key):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    #how to set key
    body = {
        "spec": {"taints":[{"effect":"NoSchedule","key":"node-role.kubernetes.io/worker"}]}
    }
    try:
        api_response = api.patch_node(node_key, body)
    except ApiException as e:
        print(e)
    
def add_node_labels(cli, node_key, **kv):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    body = {
        "metadata": {
            "labels": dict()
            }
    }
    for key in kv:
        body['metadata']['labels'][key]=kv[key]
    api_response = api.patch_node(node_key, body)
    print(api_response)

def remove_node_labels(cli, node_key, *keys):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    body = {
        "metadata": {
            "labels": dict()
            }
    }
    for key in keys:
        body['metadata']['labels'][key]=None
    api_response = api.patch_node(node_key, body)
    print(api_response)

def scale_service(cli, service, scale_spec):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    name = service.metadata.name
    namespace = service.metadata.namespace
    #TODO validate service RC or job
    body = {
        "spec": {
            "replicas": scale_spec
        }
    }
    ret = api.patch_namespaced_replication_controller_scale(
        name=name, namespace=namespace, body=body)
    print(ret)

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
    api = client.CoreV1Api(cli)
    services = get_services(cli, project_key)
    namespace = get_project_network(cli, project_key=project_key).metadata.name
    selected = []
    
    sources = [(_['name'], list(_['tasks'].keys())) for _ in [inspect_service(cli, _) for _ in services.values()]]

    if names_or_ids:
        selected = []
        for _ in sources:
            if _[0] in names_or_ids:
                selected += [(_[0], __) for __ in _[1]]
                #selected.append(_[:2])
            else:
                selected += [(_[0], __) for __ in _[1] if __ in names_or_ids]
    else:
        for _ in sources:
            selected += [(_[0], __) for __ in _[1]]
        #selected = [_[:2] for _ in sources]
    handler = LogHandler(cli)

    logs = [(service_name, handler.logs(namespace ,target, details=True, follow=follow, tail=tail, timestamps=timestamps, stdout=True, stderr=True)) for service_name, target in selected]

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
    # print(type(v1)) == kubernetes.client.api.core_v1_api.CoreV1Api
    v1 = client.CoreV1Api(cli)

    sys.exit(1)
    body = client.V1Namespace(metadata=client.V1ObjectMeta(name="hello-cluster", labels={'MLAD.PROJECT': '123', 'MLAD.PROJECT.NAME':'hello'}))
    try:
        ret = v1.create_namespace(body)
        print(f'Create Namespace [{ret.metadata.name}]')
    except ApiException as e:
        #print(f"Exception Handling v1.create_namespace => {e}", file=sys.stderr)
        if e.headers['Content-Type'] == 'application/json':
            body = json.loads(e.body)
            if body['kind'] == 'Status':
                print(f"{body['status']} : {body['message']}")
    ret = v1.list_namespace(label_selector="MLAD.PROJECT=123", watch=False)
    print('Project Networks', [_.metadata.name for _ in ret.items])
    namespace = [_.metadata.name for _ in ret.items][-1]

    #if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    #if not isinstance(network, client.models.v1_namespace.V1Namespace): raise TypeError('Parameter is not valid type.')

    project = {'name': 'test_project', 'author': 'onetop21', 'version': 'v0.0.1'}
    labels = make_base_labels("onetop21-linux@/home/onetop21/workspace/MLAppDeploy/example", 'onetop21', project, '172.20.41.118:5000')
    try:
        v1.create_namespaced_config_map(
            'hello-cluster', 
            client.V1ConfigMap(
                data=labels,
                metadata=client.V1ObjectMeta(name='what')
            )
        )
    except ApiException as e:
        #print(f"Exception Handling v1.create_namespace => {e}", file=sys.stderr)
        if e.headers['Content-Type'] == 'application/json':
            body = json.loads(e.body)
            if body['kind'] == 'Status':
                print(f"{body['status']} : {body['message']}")

    try:
        ret = v1.read_namespaced_config_map(
            "what",
            'hello-cluster', 
        )
        print(ret.data)
    except ApiException as e:
        #print(f"Exception Handling v1.create_namespace => {e}", file=sys.stderr)
        if e.headers['Content-Type'] == 'application/json':
            body = json.loads(e.body)
            if body['kind'] == 'Status':
                print(f"{body['status']} : {body['message']}")

    try:
        ret = v1.replace_namespaced_config_map(
            "what",
            'hello-cluster',
            client.V1ConfigMap(
                data={
                    "MLAD.PROJECT.AUTHOR": "kkkdoen"
                },
                metadata=client.V1ObjectMeta(name='what')
            )
        )
        print(ret.data)
    except ApiException as e:
        #print(f"Exception Handling v1.create_namespace => {e}", file=sys.stderr)
        if e.headers['Content-Type'] == 'application/json':
            body = json.loads(e.body)
            if body['kind'] == 'Status':
                print(f"{body['status']} : {body['message']}")

    try:
        ret = v1.delete_namespaced_config_map(
            "what",
            'hello-cluster'
        )
        print(ret)
    except ApiException as e:
        #print(f"Exception Handling v1.create_namespace => {e}", file=sys.stderr)
        if e.headers['Content-Type'] == 'application/json':
            body = json.loads(e.body)
            if body['kind'] == 'Status':
                print(f"{body['status']} : {body['message']}")

            
    sys.exit(1)

    def create_job(name, image, command, namespace='default', envs=None, 
                cpu='1', gpu='0',labels=None):
        cli = get_api_client()
        v1 = client.BatchV1Api(cli)
        body=client.V1Job(
            metadata=client.V1ObjectMeta(name=name,labels=labels),
            spec=client.V1JobSpec(
                backoff_limit=6,
                template=client.V1PodTemplateSpec(
                    metadata=client.V1ObjectMeta(name=name, labels=labels),
                    spec=client.V1PodSpec(
                        restart_policy='Never',
                        #termination_grace_period_seconds=30,
                        containers=[
                            client.V1Container(
                                name=name,
                                image=image,
                                #image_pull_policy='Always',
                                command=command,
                                env=envs,
                                resources=client.V1ResourceRequirements(
                                    limits={
                                        'cpu': cpu,
                                        'nvidia.com/gpu': gpu
                                    },
                                    requests={
                                        'cpu': cpu,
                                        'nvidia.com/gpu': gpu
                                    }
                                )
                            )
                        ]
                    )
                )
            )  
        )
        api_response = v1.create_namespaced_job(namespace, body)
    
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

