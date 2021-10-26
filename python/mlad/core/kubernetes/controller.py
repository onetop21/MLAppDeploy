import sys
import copy
import time
import json
import uuid
import base64
from pathlib import Path
from typing import Dict, List
from collections import defaultdict
import docker
from kubernetes.client import models
import requests
from mlad.core import exception
from mlad.core.libs import utils
from mlad.core.kubernetes.monitor import DelMonitor, Collector
from mlad.core.kubernetes.logs import LogHandler, LogCollector, LogMonitor
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

def get_auth_headers(cli, image_name=None, auth_configs=None):
    return docker_controller.get_auth_headers(docker.from_env(), image_name, auth_configs)

def get_project_networks(cli, extra_labels=[]):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    selector = ['MLAD.PROJECT.TYPE'] + (extra_labels or ['MLAD.PROJECT.TYPE=project'])
    namespaces = api.list_namespace(label_selector=','.join(selector))
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
    if network.metadata.deletion_timestamp: 
        return {'deleted': True, 'key': uuid.UUID(labels['MLAD.PROJECT'])}
    created = network.metadata.creation_timestamp
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
        'created': int(time.mktime(created.timetuple()))
    }

def create_project_network(cli, base_labels, extra_envs, credential, swarm=True, allow_reuse=False, stream=False):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
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
    default_image = base_labels['MLAD.PROJECT.IMAGE']

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
                'MLAD.PROJECT.TYPE':labels['MLAD.PROJECT.TYPE'],
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
        else:
            yield {'result': 'succeed'}

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

def get_service(cli, **kwargs):
    #service_id = k8s service uid
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    if kwargs.get('service_id'):
        service = api.list_service_for_all_namespaces(label_selector=f"uid={kwargs.get('service_id')}")
    elif kwargs.get('service_name') and kwargs.get('namespace'):
        service = api.list_namespaced_service(kwargs.get('namespace'),
                                              label_selector=f"MLAD.PROJECT.SERVICE={kwargs.get('service_name')}" )
    if not service.items:
        return None
    elif len(service.items) == 1:
        return service.items[0]

def get_service_from_kind(cli, service_name, namespace, kind):
    # get job or rc of service
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    core_api = client.CoreV1Api(cli)
    batch_api = client.BatchV1Api(cli)
    if kind == 'job':
        service = batch_api.list_namespaced_job(namespace, label_selector=f"MLAD.PROJECT.SERVICE={service_name}")
    elif kind == 'rc':
        service = core_api.list_namespaced_replication_controller(namespace,
                                                                  label_selector=f"MLAD.PROJECT.SERVICE={service_name}")
    if not service.items:
        return None
    elif len(service.items) == 1:
        return service.items[0]
    else:
        raise exception.Duplicated(f"Duplicated {kind} exists in namespace {namespace}")

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
    if pod.status.container_statuses:
        for container in pod.status.container_statuses:
            container_info = {
                'container_id': container.container_id,
                'restart': container.restart_count,
                'status': get_status(container.state),
                'ready': container.ready
            }
            pod_info['container_status'].append(container_info)
        pod_info['status'] = parse_status(pod_info['container_status'])
    else:
        pod_info['container_status'] = None
        pod_info['status'] = {
            'state': 'Waiting',
            'detail': {
                'reason': pod.status.conditions[0].reason
            }
        }
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

    kind = config_labels['MLAD.PROJECT.SERVICE.KIND']
    if kind == 'job':
        replica_ret = _get_job(cli, service_name, namespace)
    elif kind == 'rc':
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
        'replicas': replica_ret.spec.parallelism if kind == 'job' else replica_ret.spec.replicas,
        'tasks': dict([(pod.metadata.name, get_pod_info(pod)) for pod in pod_ret.items]),
        'ports': {},
        'ingress': config_labels.get('MLAD.PROJECT.INGRESS'),
        'created': replica_ret.metadata.creation_timestamp,
    }

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
                restart_policy='Never', replicas=1, cpu=None, gpu=None, mem=None, 
                labels=None, constraints={}, secrets=None):
    resources = {}
    if cpu: resources['cpu'] = str(cpu)
    if gpu: resources['nvidia.com/gpu'] = str(gpu)
    if mem: resources['memory'] = str(mem)
    # hostname: docker-desktop -> kubernetes.io/hostname: docker-desktop
    # labels.hello: world      -> hello: world
    constraints = dict([(_[7:] if _.startswith('labels.') else f"kubernetes.io/{_}", constraints[_]) for _ in constraints])

    api = client.BatchV1Api(cli)
    body=client.V1Job(
        metadata=client.V1ObjectMeta(name=name,labels=labels),
        spec=client.V1JobSpec(
            backoff_limit=0,
            parallelism=replicas,
            selector={'MLAD.PROJECT.SERVICE': name},
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(name=name, labels=labels),
                spec=client.V1PodSpec(
                    restart_policy=restart_policy,
                    termination_grace_period_seconds=10,
                    containers=[
                        client.V1Container(
                            name=name,
                            image=image,
                            image_pull_policy='Always', #TODO modify to option
                            command=command,
                            env=envs,
                            resources=client.V1ResourceRequirements(
                                limits=dict(
                                    list(resources.items())
                                ),
                                requests=dict(
                                    list(resources.items())
                                )
                            )
                        )
                    ],
                    node_selector = constraints,
                    image_pull_secrets=[client.V1LocalObjectReference(name=secrets)] if secrets else None
                )
            )
        )  
    )
    api_response = api.create_namespaced_job(namespace, body)
    return api_response

def _create_replication_controller(cli, name, image, command, namespace='default',
                                   envs=None, restart_policy='Always', 
                                   replicas=1, cpu=None, gpu=None, mem=None,
                                   labels=None, constraints={}, secrets=None):
    resources = {}
    if cpu: resources['cpu'] = str(cpu)
    if gpu: resources['nvidia.com/gpu'] = str(gpu)
    if mem: resources['memory'] = str(mem)
    constraints = dict([(_[7:] if _.startswith('labels.') else f"kubernetes.io/{_}", constraints[_]) for _ in constraints])

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
                        image_pull_policy='Always',  # TODO modify to option
                        env=envs,
                        command=command,
                        resources=client.V1ResourceRequirements(
                            limits=dict(
                                list(resources.items())
                            ),
                            requests=dict(
                                list(resources.items())
                            )
                        )
                    )],
                    node_selector = constraints,
                    image_pull_secrets=[client.V1LocalObjectReference(name=secrets)] if secrets else None
                )
            )
        )
    )
    api_response = api.create_namespaced_replication_controller(namespace, body)
    return api_response

def create_services(cli, network, services, extra_labels={}):
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
        command = f"{service['command']} {service['arguments']}".strip()
        labels = copy.copy(network_labels)
        labels.update(extra_labels)
        labels['MLAD.PROJECT.SERVICE'] = name
        
        replicas = service['deploy']['replicas'] or 1
        restart_policy = service['deploy']['restart_policy']['condition'] or 'Never'
        constraints = service['deploy']['constraints']
        rewrite_path = service['deploy']['rewrite_path']

        # Resource Spec
        resources = service['deploy']['quota']
        cpu = resources['cpus'] if 'cpus' in resources else None 
        gpu = resources['gpus'] if 'gpus' in resources else None
        mem = resources['mems'] if 'mems' in resources else None

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
        RESTART_POLICY_STORE = {
            'never': 'Never',           # JOB Controller
            'no': 'Never',              # JOB Controller
            'on_failure': 'OnFailure',  # Job Controller
            'on-failure': 'OnFailure',  # Job Controller
            'onfailure': 'OnFailure',   # Replication Controller
            'always': 'Always',
        }
        CONTROLLER_STORE = {
            'Never': 'job',
            'OnFailure': 'job',
            'Always': 'rc'
        }

        restart_policy = RESTART_POLICY_STORE.get(restart_policy.lower(), 'Never')
        kind = CONTROLLER_STORE.get(restart_policy, 'job')
        ports = service['ports'] or [80]
        
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
        }

        envs = [client.V1EnvVar(name=_.split('=', 1)[0], value=_.split('=', 1)[1])
               for _ in env]
        command = kwargs.get('command', [])
        labels = kwargs.get('labels', {})

        config_labels['MLAD.PROJECT.SERVICE']=name
        config_labels['MLAD.PROJECT.SERVICE.KIND']=kind
        ingress_path = None
        if 'expose' in service:
            if not 'service_type' in service:
                ingress_path = f"/ingress/{project_info['username']}/{project_info['name']}/{name}"
            elif service['service_type'] == 'plugin':
                ingress_path = f"/plugins/{project_info['username']}/{name}"
            envs.append(client.V1EnvVar(name='INGRESS_PATH', value=ingress_path))
            config_labels['MLAD.PROJECT.INGRESS'] = ingress_path

        # Secrets
        secrets = f"{project_base}-auth"

        try:
            if kind == 'job':
                restart_policy = kwargs.get(restart_policy, 'Never')
                ret = _create_job(
                    cli, name, image, command, 
                    namespace, envs, restart_policy, replicas,
                    cpu, gpu, mem, labels, constraints, secrets)
            elif kind == 'rc':
                restart_policy = kwargs.get(restart_policy, 'Always')
                ret = _create_replication_controller(
                    cli, name, image, command, 
                    namespace, envs, restart_policy, replicas,
                    cpu, gpu, mem, labels, constraints, secrets)
            
            ret = api.create_namespaced_service(namespace, client.V1Service(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels
                ),
                spec=client.V1ServiceSpec(
                    selector={'MLAD.PROJECT.SERVICE': name},
                    ports=[client.V1ServicePort(port=_) for _ in ports]
                )
            ))
            if ingress_path:
                ingress_ret = create_ingress(cli, namespace, name, service['expose'], ingress_path,
                                             rewrite=rewrite_path)

            label_body = {
                "metadata": {
                    "labels": {'uid':ret.metadata.uid}
                    }
            }
            temp_ret = api.patch_namespaced_service(name, namespace, label_body)
            instances.append(temp_ret)
            create_config_labels(cli, f'service-{name}-labels', namespace, config_labels)
        except ApiException as e:
            print(f"Exception Handling CoreV1Api => {e}", file=sys.stderr)
            if e.headers['Content-Type'] == 'application/json':
                body = json.loads(e.body)
                if body['kind'] == 'Status':
                    msg = body['message']
                    status = body['code']
                else:
                    msg = str(e)
                    status = 500
            err_msg = f'Failed to create services: {msg}'
            raise exception.APIError(err_msg, status)
    return instances

def remove_containers(cli, containers):
    return docker_controller.remove_containers(docker.from_env(), containers)

def _delete_job(cli, name, namespace):
    api = client.BatchV1Api(cli)
    return api.delete_namespaced_job(name, namespace, propagation_policy='Foreground')

def _delete_replication_controller(cli, name, namespace):
    api = client.CoreV1Api(cli)
    return api.delete_namespaced_replication_controller(name, 
        namespace, propagation_policy='Foreground')

def remove_services(cli, services, disconnHandler=None, timeout=0xFFFF, stream=False):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    network_api = client.NetworkingV1beta1Api(cli)

    def _get_service_info(service):
        inspect = inspect_service(cli, service)
        service_name = inspect['name']
        namespace = service.metadata.namespace
        targets = list(inspect['tasks'].keys())

        config_labels = get_config_labels(cli, service,
            f'service-{service_name}-labels')
        kind = config_labels['MLAD.PROJECT.SERVICE.KIND']
        return service_name, namespace, kind, targets

    service_to_check=[]
    for service in services:
        service_name, namespace, kind, _ = _get_service_info(service)
        service_to_check.append((service_name, namespace, kind, _))

    # For check service deleted
    collector = Collector()
    monitor = DelMonitor(cli, collector, service_to_check, namespace)
    monitor.start()
    disconnHandler.add_callback(lambda: monitor.stop())

    for service in service_to_check:
        service_name, namespace, kind, _ = service
        print(f"Stop {service_name}...")
        ret = api.delete_namespaced_service(service_name, namespace)
        if kind == 'job':
            ret = _delete_job(cli, service_name, namespace)
        elif kind == 'rc':
            ret = _delete_replication_controller(cli, service_name, namespace)
    
        try:
            #check ingress exists
            ingress = network_api.list_namespaced_ingress(namespace)
            if service_name in ingress.items:
                ingress_ret = network_api.delete_namespaced_ingress(service_name, namespace)
        except ApiException as e:
            print("Exception when calling ExtensionsV1beta1Api->delete_namespaced_ingress: %s\n" % e)

    def resp_from_collector(collector):
        for _ in collector:
            yield  _

    if stream:
        return resp_from_collector(collector)
    else:
        #TBD
        removed = False
        for service in services:
            service_removed = False
            name, namespace, kind = _get_service_info(service)
            if not get_service_from_kind(cli, name, namespace, kind) and \
                    not get_service(cli, service_name=name, namespace=namespace):
                service_removed = True
            else:
                service_removed = False
                removed &= service_removed
        return (removed, (_ for _ in resp_stream()))


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
    return dict(
        [(_.metadata.name, _.metadata) for _ in api.list_node().items]
    )

def get_node(cli, node_key):
    if not isinstance(cli, client.api_client.ApiClient): raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    nodes = api.list_node(field_selector=f"metadata.name={node_key}")
    if nodes.items: 
        return nodes.items[0]
    else:
        #print(f'Cannot find node "{node_key}"', file=sys.stderr)
        raise exception.NotFound(f'Cannot find node "{node_key}"')

def inspect_node(node):
    if not isinstance(node, client.models.v1_node.V1Node): raise TypeError('Parameter is not valid type.')
    hostname = node.metadata.labels['kubernetes.io/hostname']
    availability = 'active' if node.spec.taints == None else 'pause'
    platform = node.metadata.labels['kubernetes.io/os']    
    arch = node.metadata.labels['kubernetes.io/arch']
    resources = node.status.capacity
    engine_version = node.status.node_info.kubelet_version
    role = [_.split('/')[-1] for _ in node.metadata.labels if _.startswith('node-role')]
    state = node.status.conditions[-1].type
    addr = node.status.addresses[0].address
    labels = dict([(_, node.metadata.labels[_]) for _ in node.metadata.labels if not 'kubernetes.io/' in _])

    return {
        'id': node.metadata.uid,
        'hostname': hostname,
        'labels': labels,
        'role': role,
        'availability': availability,
        'platform': platform,
        'arch': arch,
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
    name = service.metadata.name
    namespace = service.metadata.namespace
    config_labels = get_config_labels(cli, service, f'service-{name}-labels')
    kind = config_labels['MLAD.PROJECT.SERVICE.KIND']
    if kind == 'job':
        api = client.BatchV1Api(cli)
        body = {
            "spec": {
                "parallelism": scale_spec
            }
        }
        ret = api.patch_namespaced_job(
            name=name, namespace=namespace, body=body)
    elif kind == 'rc':
        api = client.CoreV1Api(cli)
        body = {
            "spec": {
                "replicas": scale_spec
            }
        }
        ret = api.patch_namespaced_replication_controller_scale(
            name=name, namespace=namespace, body=body)
    return ret

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

def get_service_with_names_or_ids(cli, project_key, names_or_ids=[]):
    # get running services with service or pod name
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
                names_or_ids.remove(_[0])
            else:
                #check task ids of svc
                for __ in _[1]:
                    if __ in names_or_ids:
                        selected += [(_[0], __)]
                        names_or_ids.remove(__)
        if names_or_ids:
            raise exception.NotFound(f"Cannot find name or task in project: {', '.join(names_or_ids)}")

    else:
        for _ in sources:
            selected += [(_[0], __) for __ in _[1]]

    # check whether targets are pending or not
    targets = []
    for target in selected:
        pod = api.read_namespaced_pod(name=target[1], namespace=namespace)
        phase = get_pod_info(pod)['phase']
        if not phase == 'Pending':
            targets.append(target)
        else:
            print(f'Cannot get logs of pending service: {target[1]}')

    if not targets:
        raise exception.NotFound("Cannot find running services")

    return targets

def get_project_logs(cli, project_key, tail='all', follow=False, timestamps=False,
                     selected=False, disconnHandler=None, targets=[]):
    api = client.CoreV1Api(cli)
    services = get_services(cli, project_key)
    namespace = get_project_network(cli, project_key=project_key).metadata.name

    handler = LogHandler(cli)

    logs = [(target, handler.logs(namespace, target, details=True, follow=follow,
                                  tail=tail, timestamps=timestamps, stdout=True, stderr=True))
            for service_name, target in targets]

    if len(logs):
        with LogCollector() as collector:
            for name, log in logs:
                collector.add_iterable(log, name=name, timestamps=timestamps)
            # Register Disconnect Callback
            disconnHandler.add_callback(lambda: handler.close())
            if follow and not selected:
                last_resource = None
                monitor = LogMonitor(cli, handler, collector, namespace, last_resource=last_resource,
                                     follow=follow, tail=tail, timestamps=timestamps)
                monitor.start()
                disconnHandler.add_callback(lambda: monitor.stop())
            yield from collector
    else:
        print('Cannot find running containers.', file=sys.stderr)

def create_ingress(cli, namespace, service_name, port, base_path='/', rewrite=False):
    api = client.NetworkingV1beta1Api(cli)
    annotations = {
        "kubernetes.io/ingress.class": "nginx",
        "nginx.ingress.kubernetes.io/proxy-body-size": "0",
        "nginx.ingress.kubernetes.io/proxy-read-timeout": "600",
        "nginx.ingress.kubernetes.io/proxy-send-timeout": "600",
    }
    if rewrite:
        annotations.update({
            "nginx.ingress.kubernetes.io/rewrite-target": "/$2"
        })
    body = client.NetworkingV1beta1Ingress(
        api_version="networking.k8s.io/v1beta1",
        kind="Ingress",
        metadata=client.V1ObjectMeta(name=service_name, annotations=annotations),
        spec=client.NetworkingV1beta1IngressSpec(
            rules=[client.NetworkingV1beta1IngressRule(
                #host="example.com",
                http=client.NetworkingV1beta1HTTPIngressRuleValue(
                    paths=[client.NetworkingV1beta1HTTPIngressPath(
                        path=f"{base_path}(/|$)(.*)" if rewrite else base_path,
                        backend=client.NetworkingV1beta1IngressBackend(
                            service_port=port,
                            service_name=service_name)
                        )]
                    )
                )
            ]
        )
    )
    # Creation of the Deployment in specified namespace
    # (Can replace "default" with a namespace you may have created)
    return api.create_namespaced_ingress(
        namespace=namespace,
        body=body
    )

def parse_mem(str_mem):
    # Ki to Mi
    if str_mem.endswith('Ki'):
        mem = float(str_mem[:-2]) / 1024
    else:
        #TODO Other units may need to be considered
        mem = float(str_mem)
    return mem

def parse_cpu(str_cpu):
    # nano to core
    if str_cpu.endswith('n'):
        cpu = float(str_cpu[:-1]) / 10 ** 9
    else:
        # TODO Other units may need to be considered
        cpu = float(str_cpu)
    return cpu

def get_node_resources(cli, node):
    if not isinstance(node, client.models.v1_node.V1Node): raise TypeError('Parameter is not valid type.')
    api = client.CustomObjectsApi(cli)
    v1_api = client.CoreV1Api(cli)
    nodes = api.list_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes")
    name = node.metadata.name

    allocatable = node.status.allocatable
    mem = parse_mem(allocatable['memory']) #Mi
    cpu = int(allocatable['cpu']) #core
    gpu = int(allocatable['nvidia.com/gpu']) if 'nvidia.com/gpu' in allocatable else 0 #cnt

    try:
        metric = api.get_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes", name)
    except ApiException as e:
        if e.headers['Content-Type'] == 'application/json':
            body = json.loads(e.body)
            if body['kind'] == 'Status':
                print(f"{body['status']} : {body['message']}")
        used_mem = None
        used_cpu = None
    else:
        used_mem = parse_mem(metric['usage']['memory'])
        used_cpu = parse_cpu(metric['usage']['cpu'])
    used_gpu = 0

    selector = (f'spec.nodeName={name},status.phase!=Succeeded,status.phase!=Failed')
    pods = v1_api.list_pod_for_all_namespaces(field_selector=selector)
    for pod in pods.items:
        for container in pod.spec.containers:
            requests = defaultdict(lambda: '0', container.resources.requests or {})
            used_gpu += int(requests['nvidia.com/gpu'])

    return {
        'mem': {'capacity': mem, 'used': used_mem, 'allocatable': mem-used_mem},
        'cpu': {'capacity': cpu, 'used': used_cpu, 'allocatable': cpu-used_cpu},
        'gpu': {'capacity': gpu, 'used': used_gpu, 'allocatable': gpu-used_gpu},
    }

def get_project_resources(cli, project_key):
    api = client.CustomObjectsApi(cli)
    v1_api = client.CoreV1Api(cli)
    res = {}
    services = get_services(cli, project_key)

    def gpu_usage(pod):
        used = 0
        for container in pod.spec.containers:
            requests = defaultdict(lambda: '0', container.resources.requests or {})
            used += int(requests['nvidia.com/gpu'])
        return used


    for name, service in services.items():
        resource = defaultdict(lambda: 0)
        namespace = service.metadata.namespace

        field_selector = (f'status.phase!=Succeeded,status.phase!=Failed')
        pods = v1_api.list_namespaced_pod(namespace,
                                          label_selector=f'MLAD.PROJECT.SERVICE={name}',
                                          field_selector=field_selector)
        for pod in pods.items:
            pod_name = pod.metadata.name
            try:
                metric = api.get_namespaced_custom_object("metrics.k8s.io", "v1beta1", namespace,
                                                        "pods", pod_name)
            except ApiException as e:
                if e.headers['Content-Type'] == 'application/json':
                    body = json.loads(e.body)
                    if body['kind'] == 'Status':
                        print(f"{body['status']} : {body['message']}")
                resource['cpu'] = None
                resource['mem'] = None
                resource['gpu'] += gpu_usage(pod)
                break

            for _ in metric['containers']:
                resource['cpu'] += parse_cpu(_['usage']['cpu'])
                resource['mem'] += parse_mem(_['usage']['memory'])
            resource['gpu'] += gpu_usage(pod)

        res[name] = {'mem': resource['mem'], 'cpu': resource['cpu'], 'gpu': resource['gpu']}
    return res

if __name__ == '__main__':
    cli = get_api_client()
    # print(type(v1)) == kubernetes.client.api.core_v1_api.CoreV1Api
    v1 = client.CoreV1Api(cli)

    name = 'test2'
    image = 'ubuntu'
    namespace = 'kkkdeon-example-89de634c05-cluster'
    command= ["/bin/bash", "-ec", "while :; do echo 'test pod log'; sleep 5 ; done"]

    labels = {'MLAD.PROJECT.SERVICE': name}

    _create_job(cli, name, image, command, namespace, labels=labels)
    ret = v1.create_namespaced_service(namespace, client.V1Service(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=labels
        ),
        spec=client.V1ServiceSpec(
            selector={'MLAD.PROJECT.SERVICE': name},
            ports=[client.V1ServicePort(port=5555)]
        )
    ))
    sys.exit(1)

    from kubernetes import watch

    w = watch.Watch()
    namespace = 'kkkdeon-example-6a7c58fd94-cluster'
    for e in w.stream(v1.list_namespaced_pod, namespace=namespace):
        print(e['type'])
        print(e['object'].status.phase)

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
    labels = utils.base_labels("onetop21-linux@/home/onetop21/workspace/MLAppDeploy/example", 'onetop21', project, '172.20.41.118:5000')
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
                        termination_grace_period_seconds=10,
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


