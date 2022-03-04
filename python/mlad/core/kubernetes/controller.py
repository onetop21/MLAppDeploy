import sys
import copy
import time
import json
import uuid

from multiprocessing.pool import ThreadPool
from typing import Union, Optional
from collections import defaultdict

from kubernetes import client, config, watch
from kubernetes.client.api_client import ApiClient
from kubernetes.client.rest import ApiException

from mlad.core import exceptions
from mlad.core.exceptions import NamespaceAlreadyExistError, DeprecatedError, InvalidAppError, \
    InvalidMetricUnitError
from mlad.core.libs import utils
from mlad.core.kubernetes.monitor import DelMonitor, Collector
from mlad.core.kubernetes.logs import LogHandler, LogCollector, LogMonitor


# https://github.com/kubernetes-client/python/blob/release-11.0/kubernetes/docs/CoreV1Api.md

SHORT_LEN = 10


config_envs = {'APP', 'AWS_ACCESS_KEY_ID', 'AWS_REGION', 'AWS_SECRET_ACCESS_KEY', 'DB_ADDRESS',
               'DB_PASSWORD', 'DB_USERNAME', 'MLAD_ADDRESS', 'MLAD_SESSION', 'PROJECT',
               'PROJECT_ID', 'PROJECT_KEY', 'S3_ENDPOINT', 'S3_USE_HTTPS', 'S3_VERIFY_SSL',
               'USERNAME'}


def get_api_client(config_file='~/.kube/config', context=None):
    try:
        if context:
            return config.new_client_from_config(context=context)
        else:

            return config.new_client_from_config(config_file=config_file)
    except config.config_exception.ConfigException:
        pass
    try:
        config.load_incluster_config()
        # If Need, set configuration parameter from client.Configuration
        return ApiClient()
    except config.config_exception.ConfigException:
        return None


def get_current_context():
    try:
        current_context = config.list_kube_config_contexts()[1]
    except config.config_exception.ConfigException as e:
        raise exceptions.APIError(str(e), 404)
    return current_context['name']


DEFAULT_CLI = get_api_client()


def check_project_key(project_key, app, cli=DEFAULT_CLI):
    inspect_key = str(inspect_app(app, cli=cli)['key'])
    if project_key == inspect_key:
        return True
    else:
        raise InvalidAppError(project_key, app.metadata.name)


def get_namespaces(extra_labels=[], cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    selector = ['MLAD.PROJECT'] + extra_labels
    namespaces = api.list_namespace(label_selector=','.join(selector))
    return dict([(_.metadata.name, _) for _ in namespaces.items])


def get_namespace(cli=DEFAULT_CLI, **kwargs):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    if kwargs.get('project_key'):
        namespaces = api.list_namespace(label_selector=f"MLAD.PROJECT={kwargs.get('project_key')}")
    elif kwargs.get('project_id'):
        namespaces = api.list_namespace(
            label_selector=f"MLAD.PROJECT.ID={kwargs.get('project_id')}")
    elif kwargs.get('namespace_id'):
        all_namespaces = api.list_namespace(label_selector="MLAD.PROJECT")
        namespaces = list(
            filter(lambda _: _.metadata.uid == kwargs.get('namespace_id'), all_namespaces)
        )
    else:
        raise TypeError('At least one parameter is required.')
    if not namespaces.items:
        return None
    elif len(namespaces.items) == 1:
        return namespaces.items[0]
    else:
        raise exceptions.Duplicated(
            "Need to remove namespaces or down project, because exists duplicated namespaces.")


def get_labels(obj):
    # TODO to be modified
    if isinstance(obj, client.models.v1_namespace.V1Namespace):
        return obj.metadata.labels
    elif isinstance(obj, client.models.v1_replication_controller.V1ReplicationController):
        return obj.metadata.labels
    elif isinstance(obj, client.models.v1_service.V1Service):
        return obj.metadata.labels
    else:
        raise TypeError('Parameter is not valid type.')


def get_config_labels(namespace, key, cli=DEFAULT_CLI):
    # key='project-labels', 'app-{name}-labels'
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    if isinstance(namespace, client.models.v1_namespace.V1Namespace):
        namespace = namespace.metadata.name
    ret = api.read_namespaced_config_map(key, namespace)
    return ret.data


def create_config_labels(cli, key, namespace, labels):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    ret = api.create_namespaced_config_map(
        namespace,
        client.V1ConfigMap(
            data=labels,
            metadata=client.V1ObjectMeta(name=key)
        )
    )
    return ret.data


def inspect_namespace(namespace, cli=DEFAULT_CLI):
    if not isinstance(namespace, client.models.v1_namespace.V1Namespace):
        raise TypeError('Parameter is not valid type.')
    labels = get_labels(namespace)
    if namespace.metadata.deletion_timestamp:
        return {'deleted': True, 'key': labels['MLAD.PROJECT']}
    config_labels = get_config_labels(namespace, 'project-labels', cli)
    hostname, path = config_labels['MLAD.PROJECT.WORKSPACE'].split(':')

    return {
        'key': labels['MLAD.PROJECT'],
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': config_labels['MLAD.PROJECT.USERNAME'],
        'name': config_labels['MLAD.PROJECT.NAMESPACE'],
        'project': labels['MLAD.PROJECT.NAME'],
        'id': uuid.UUID(config_labels['MLAD.PROJECT.ID']),
        'version': config_labels['MLAD.PROJECT.VERSION'],
        'base': config_labels['MLAD.PROJECT.BASE'],
        'image': config_labels['MLAD.PROJECT.IMAGE'],
        'kind': config_labels.get('MLAD.PROJECT.KIND', 'Deployment'),
        'created': namespace.metadata.creation_timestamp,
        'project_yaml': (namespace.metadata.annotations or dict()).get('MLAD.PROJECT.YAML', '{}')
    }


def get_project_session(namespace, cli=DEFAULT_CLI):
    if not isinstance(namespace, client.models.v1_namespace.V1Namespace):
        raise TypeError('Parameter is not valid type.')
    config_labels = get_config_labels(namespace, 'project-labels', cli)
    return config_labels['MLAD.PROJECT.SESSION']


def create_namespace(base_labels, extra_envs, project_yaml, credential,
                     allow_reuse=False, stream=False, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    project_key = base_labels['MLAD.PROJECT']
    namespace = get_namespace(cli, project_key=project_key)
    if namespace is not None:
        if allow_reuse:
            if stream:
                def resp_stream():
                    yield {
                        'result': 'exists',
                        'name': namespace.metadata.name,
                        'id': namespace.metadata.uid
                    }
                return resp_stream()
            else:
                stream_out = (_ for _ in resp_stream())
                return (namespace, stream_out)
        raise NamespaceAlreadyExistError(project_key)
    basename = base_labels['MLAD.PROJECT.BASE']

    def resp_stream():
        namespace_name = f"{basename}-cluster"
        try:
            message = f"Create a namespace [{namespace_name}]...\n"
            yield {'stream': message}
            labels = copy.deepcopy(base_labels)
            labels.update({
                'MLAD.PROJECT.NAMESPACE': namespace_name,
                'MLAD.PROJECT.ID': str(utils.generate_unique_id()),
                'MLAD.PROJECT.ENV': utils.encode_dict(extra_envs),
            })
            keys = {
                'MLAD.PROJECT': labels['MLAD.PROJECT'],
                'MLAD.PROJECT.NAME': labels['MLAD.PROJECT.NAME'],
            }
            annotations = {
                'MLAD.PROJECT.YAML': json.dumps(project_yaml)
            }
            api.create_namespace(
                client.V1Namespace(
                    metadata=client.V1ObjectMeta(
                        name=namespace_name,
                        labels=keys,
                        annotations=annotations
                    )
                )
            )
            create_config_labels(cli, 'project-labels', namespace_name, labels)
            # AuthConfig
            api.create_namespaced_secret(
                namespace_name,
                client.V1Secret(
                    metadata=client.V1ObjectMeta(name=f"{basename}-auth"),
                    type='kubernetes.io/dockerconfigjson',
                    data={'.dockerconfigjson': credential}
                )
            )
        except ApiException as e:
            message = f"Failed to create namespace.\n{e}\n"
            yield {'result': 'failed', 'stream': message}
    if stream:
        return resp_stream()
    else:
        stream_out = (_ for _ in resp_stream())
        return (get_namespace(cli, project_key=project_key), stream_out)


def remove_namespace(namespace, timeout=0xFFFF, stream=False, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    if not isinstance(namespace, client.models.v1_namespace.V1Namespace):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    spec = inspect_namespace(namespace, cli)
    api.delete_namespace(namespace.metadata.name)

    def resp_stream():
        removed = False
        for tick in range(timeout):
            if not get_namespace(cli, project_key=spec['key']):
                removed = True
                break
            else:
                padding = '\033[1A\033[K' if tick else ''
                message = f"{padding}Wait for removing the namespace...[{tick}s]\n"
                yield {'stream': message}
                time.sleep(1)
        if not removed:
            message = 'Failed to remove namespace.\n'
            yield {'result': 'failed', 'stream': message}
        else:
            yield {'result': 'succeed'}

    if stream:
        return resp_stream()
    else:
        return (not get_namespace(cli, project_key=spec['key']), (_ for _ in resp_stream()))


def update_namespace(namespace, update_yaml, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    if not isinstance(namespace, client.models.v1_namespace.V1Namespace):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    name = namespace.metadata.name
    namespace.metadata.annotations['MLAD.PROJECT.YAML'] = json.dumps(update_yaml)
    try:
        api.patch_namespace(name, namespace)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find namespace {name}.')
        else:
            raise exceptions.APIError(msg, status)


def get_deployment(name, namespace, cli=DEFAULT_CLI):
    api = client.AppsV1Api(cli)
    try:
        res = api.read_namespaced_deployment(name, namespace)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find deployment "{name}" in "{namespace}".')
        else:
            raise exceptions.APIError(msg, status)
    return res


def get_daemonset(name, namespace, cli=DEFAULT_CLI):
    api = client.AppsV1Api(cli)
    try:
        res = api.read_namespaced_daemon_set(name, namespace)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find daemonset "{name}" in "{namespace}".')
        else:
            raise exceptions.APIError(msg, status)
    return res


def get_app(name, namespace, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    key = f'app-{name}-labels'
    config_labels = get_config_labels(namespace, key, cli)
    kind = config_labels['MLAD.PROJECT.APP.KIND']
    name = config_labels['MLAD.PROJECT.APP']
    app = get_app_from_kind(cli, name, namespace, kind)
    return app


def get_apps(project_key=None, extra_filters={}, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    batch_api = client.BatchV1Api(cli)
    apps_api = client.AppsV1Api(cli)
    filters = [f'MLAD.PROJECT={project_key}' if project_key else 'MLAD.PROJECT']
    filters += [f'{key}={value}' for key, value in extra_filters.items()]

    apps = []
    apps += batch_api.list_job_for_all_namespaces(label_selector=','.join(filters)).items
    apps += apps_api.list_deployment_for_all_namespaces(label_selector=','.join(filters)).items

    if project_key:
        return dict([(_.metadata.labels['MLAD.PROJECT.APP'], _) for _ in apps])
    else:
        return dict([(f'{_.metadata.labels["MLAD.PROJECT"]}/{_.metadata.name}', _)
                     for _ in apps])


def get_service(name, namespace, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    try:
        res = api.read_namespaced_service(name, namespace)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find deployment "{name}" in "{namespace}".')
        else:
            raise exceptions.APIError(msg, status)
    return res


def get_app_service(cli, namespace, name):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    service = api.list_namespaced_service(
        namespace, label_selector=f"MLAD.PROJECT.APP={name}")
    if not service.items:
        return None
    elif len(service.items) == 1:
        return service.items[0]


def get_app_from_kind(cli, app_name, namespace, kind):
    # get job or rc of app
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    batch_api = client.BatchV1Api(cli)
    apps_api = client.AppsV1Api(cli)
    if kind == 'Job':
        app = batch_api.list_namespaced_job(
            namespace, label_selector=f"MLAD.PROJECT.APP={app_name}")
    elif kind == 'Service':
        app = apps_api.list_namespaced_deployment(
            namespace, label_selector=f"MLAD.PROJECT.APP={app_name}")

    if not app.items:
        return None
    elif len(app.items) == 1:
        return app.items[0]
    else:
        raise exceptions.Duplicated(f"Duplicated {kind} exists in namespace {namespace}")


def get_pod_events(pod, cli=DEFAULT_CLI):
    api = client.CoreV1Api(cli)
    name = pod.metadata.name
    namespace = pod.metadata.namespace

    events = api.list_namespaced_event(namespace, field_selector='type=Warning').items
    return [{'name': name, 'message': e.message, 'datetime': e.metadata.creation_timestamp}
            for e in events if e.involved_object.name == name]


def get_pod_info(pod):
    if not isinstance(pod, client.models.v1_pod.V1Pod):
        raise TypeError('Parameter is not valid type.')

    pod_info = {
        'name': pod.metadata.name,
        'namespace': pod.metadata.namespace,
        'created': pod.metadata.creation_timestamp,
        'container_status': list(),
        'status': dict(),
        'node': pod.spec.node_name,
        # Pending, Running, Succeeded, Failed, Unknown
        'phase': pod.status.phase,
        'events': get_pod_events(pod),
        'restart': 0
    }

    def get_status(container_state):
        if container_state.running:
            return {'state': 'Running', 'detail': None}
        if container_state.terminated:
            return {
                'state': 'Terminated',
                'detail': {
                    'reason': container_state.terminated.reason,
                    'finished': container_state.terminated.finished_at
                }
            }
        if container_state.waiting:
            return {
                'state': 'Waiting',
                'detail': {
                    'reason': container_state.waiting.reason
                }
            }

    def parse_status(containers):
        status = {'state': 'Running', 'detail': None}
        # if not running container exits, return that
        completed = 0
        for _ in containers:
            if _['status']['state'] == 'Waiting':
                return _['status']
            elif _['status']['state'] == 'Terminated':
                if _['status']['detail']['reason'] == 'Completed':
                    completed += 1
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
            pod_info['restart'] += container_info['restart']
        pod_info['status'] = parse_status(pod_info['container_status'])
    else:
        pod_info['container_status'] = None
        pod_info['status'] = {
            'state': 'Waiting',
            'detail': {
                'reason': pod.status.conditions[0].reason if pod.status.conditions
                else pod.status.reason
            }
        }
    return pod_info


def inspect_app(app, cli=DEFAULT_CLI):
    kind = None
    if isinstance(app, client.models.v1_deployment.V1Deployment):
        kind = 'Service'
    elif isinstance(app, client.models.v1_job.V1Job):
        kind = 'Job'
    else:
        raise TypeError('Parameter is not valid type.')

    api = client.CoreV1Api(cli)

    name = app.metadata.name
    namespace = app.metadata.namespace
    config_labels = get_config_labels(namespace, f'app-{name}-labels', cli)

    pod_ret = api.list_namespaced_pod(namespace,
                                      label_selector=f'MLAD.PROJECT.APP={name}')

    hostname, path = config_labels.get('MLAD.PROJECT.WORKSPACE', ':').split(':')
    pod_spec = app.spec.template.spec
    service = get_app_service(cli, namespace, name)
    try:
        ingress = json.loads(config_labels.get('MLAD.PROJECT.INGRESS', '[]'))
    except json.decoder.JSONDecodeError:
        path = config_labels.get('MLAD.PROJECT.INGRESS', '')
        ingress = []
        if path != '':
            ingress.append({'port': '-', 'path': path})

    spec = {
        'key': config_labels['MLAD.PROJECT'] if config_labels.get(
            'MLAD.VERSION') else '',
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': config_labels.get('MLAD.PROJECT.USERNAME'),
        'namespace': config_labels.get('MLAD.PROJECT.NAMESPACE'),
        'project': config_labels.get('MLAD.PROJECT.NAME'),
        'project_id': uuid.UUID(config_labels['MLAD.PROJECT.ID']) if config_labels.get(
            'MLAD.VERSION') else '',
        'version': config_labels.get('MLAD.PROJECT.VERSION'),
        'base': config_labels.get('MLAD.PROJECT.BASE'),
        # Replace from labels['MLAD.PROJECT.IMAGE']
        'image': pod_spec.containers[0].image,
        'env': [{'name': e.name, 'value': e.value} for e in pod_spec.containers[0].env],
        'id': app.metadata.uid,
        'name': config_labels.get('MLAD.PROJECT.APP'),
        'replicas': app.spec.parallelism if kind == 'Job' else app.spec.replicas,
        'tasks': dict([(pod.metadata.name, get_pod_info(pod)) for pod in pod_ret.items]),
        'ports': [port_spec.port for port_spec in service.spec.ports] if service is not None else [],
        'ingress': ingress,
        'created': app.metadata.creation_timestamp,
        'kind': config_labels.get('MLAD.PROJECT.APP.KIND'),
    }

    return spec


def inspect_apps(apps):
    results = []
    with ThreadPool(len(apps)) as pool:
        for app in apps:
            results.append(pool.apply_async(inspect_app, (app,)))
        return [result.get() for result in results]


def _mounts_to_V1Volume(name, mounts, pvc_specs):
    _mounts = []
    _volumes = []
    if mounts:
        for i, _ in enumerate(mounts):
            host_path, mount_path = _.split(":")[0], _.split(":")[1]
            volume_name = f'{name}-mnt{i}'
            _mounts.append(
                client.V1VolumeMount(
                    name=volume_name,
                    mount_path=mount_path,
                )
            )
            _volumes.append(
                client.V1Volume(
                    name=volume_name,
                    host_path=client.V1HostPathVolumeSource(
                        path=host_path
                    )
                )
            )
    for pvc_spec in pvc_specs:
        name = pvc_spec['name']
        mount_path = pvc_spec['mountPath']
        volume_name = f'{name}-vol'
        _mounts.append(
            client.V1VolumeMount(
                name=volume_name,
                mount_path=mount_path
            )
        )
        _volumes.append(
            client.V1Volume(
                name=volume_name,
                persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                    claim_name=name
                )
            )
        )
    return _mounts, _volumes


def _resources_to_V1Resource(type='Quota', resources=None):
    limits = {'nvidia.com/gpu': 0}
    requests = {'nvidia.com/gpu': 0}
    if type == 'Quota' and resources is not None:
        for type in resources:
            if type == 'cpu':
                requests['cpu'] = str(resources['cpu']) if resources[type] else None
            elif type == 'gpu':
                requests['nvidia.com/gpu'] = str(resources['gpu']) if resources[type] else None
            elif type == 'mem':
                requests['memory'] = str(resources['mem']) if resources[type] else None
        limits = requests
    elif type == 'Resources':
        if 'limits' in resources:
            for type in resources['limits']:
                if type == 'cpu':
                    limits['cpu'] = str(resources['limits']['cpu'])
                elif type == 'gpu':
                    limits['nvidia.com/gpu'] = str(resources['limits']['gpu'])
                elif type == 'mem':
                    limits['mem'] = str(resources['limits']['mem'])
        if 'requests' in resources:
            for type in resources['requests']:
                if type == 'cpu':
                    requests['cpu'] = str(resources['requests']['cpu'])
                elif type == 'gpu':
                    requests['nvidia.com/gpu'] = str(resources['requests']['gpu'])
                elif type == 'mem':
                    requests['mem'] = str(resources['requests']['mem'])
    return client.V1ResourceRequirements(limits=limits, requests=requests)


def _constraints_to_labels(constraints):
    _constraints = {}
    if constraints:
        for k, v in constraints.items():
            if constraints[k]:
                if k == 'hostname':
                    _constraints["kubernetes.io/hostname"] = v
                else:
                    for _ in v:
                        _constraints[_] = str(v[_])
    return _constraints


def _depends_to_init_container(depends, envs):
    env = [*envs, _create_V1Env('DEPENDENCY_SPECS', json.dumps(depends))]
    return client.V1Container(
        name='dependency-check-container',
        image='ghcr.io/onetop21/mlappdeploy/api-server:4d98887',
        image_pull_policy='Always',
        command=['python', '-m', 'mlad.core.dependency'],
        env=env
    )


def _create_job(name, image, command, namespace='default', restart_policy='Never',
                envs=None, mounts=None, pvc_specs=[], parallelism=None, completions=None, quota=None,
                resources=None, init_containers=None, labels=None, constraints=None, secrets=None, cli=DEFAULT_CLI):

    _resources = _resources_to_V1Resource(type='Resources', resources=resources) if resources \
        else _resources_to_V1Resource(resources=quota)

    _constraints = _constraints_to_labels(constraints)

    _mounts, _volumes = _mounts_to_V1Volume(name, mounts, pvc_specs)

    api = client.BatchV1Api(cli)
    body = client.V1Job(
        metadata=client.V1ObjectMeta(name=name, labels=labels),
        spec=client.V1JobSpec(
            backoff_limit=0,
            parallelism=parallelism,
            completions=completions,
            selector={'MLAD.PROJECT.APP': name},
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(name=name, labels=labels),
                spec=client.V1PodSpec(
                    restart_policy=restart_policy,
                    termination_grace_period_seconds=10,
                    init_containers=init_containers,
                    containers=[
                        client.V1Container(
                            name=name,
                            image=image,
                            image_pull_policy='Always',
                            command=command,
                            env=envs,
                            resources=_resources,
                            volume_mounts=_mounts
                        )
                    ],
                    volumes=_volumes,
                    node_selector=_constraints,
                    image_pull_secrets=[client.V1LocalObjectReference(name=secrets)]
                    if secrets else None
                )
            )
        )
    )
    api_response = api.create_namespaced_job(namespace, body)
    return api_response


def _create_deployment(name, image, command, namespace='default',
                       envs=None, mounts=None, pvc_specs=[], replicas=1, quota=None, resources=None,
                       init_containers=None, labels=None, constraints=None, secrets=None, cli=DEFAULT_CLI):

    _resources = _resources_to_V1Resource(type='Resources', resources=resources) if resources \
        else _resources_to_V1Resource(resources=quota)

    _constraints = _constraints_to_labels(constraints)

    _mounts, _volumes = _mounts_to_V1Volume(name, mounts, pvc_specs)

    api = client.AppsV1Api(cli)
    body = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=name,
            labels=labels
        ),
        spec=client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(
                match_labels={'MLAD.PROJECT.APP': name}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    name=name,
                    labels=labels
                ),
                spec=client.V1PodSpec(
                    restart_policy='Always',
                    init_containers=init_containers,
                    containers=[client.V1Container(
                        name=name,
                        image=image,
                        image_pull_policy='Always',
                        env=envs,
                        command=command,
                        resources=_resources,
                        volume_mounts=_mounts
                    )],
                    volumes=_volumes,
                    node_selector=_constraints,
                    image_pull_secrets=[client.V1LocalObjectReference(name=secrets)]
                    if secrets else None
                )
            )
        )
    )

    api_response = api.create_namespaced_deployment(namespace, body)
    return api_response


def _create_pv(name: str, pv_index: int, pv_mount, cli=DEFAULT_CLI):
    api = client.CoreV1Api(cli)
    api.create_persistent_volume(
        client.V1PersistentVolume(
            api_version='v1',
            kind='PersistentVolume',
            metadata=client.V1ObjectMeta(
                name=f'{name}-{pv_index}-pv',
                labels={
                    'mount': f'{name}-{pv_index}',
                    'MLAD.PROJECT.APP': name
                }
            ),
            spec=client.V1PersistentVolumeSpec(
                capacity={'storage': '10Gi'},
                access_modes=['ReadWriteMany'],
                mount_options=pv_mount['options'],
                nfs=client.V1NFSVolumeSource(
                    path=pv_mount['serverPath'],
                    server=pv_mount['server']
                )
            )
        )
    )


def _delete_pvs(name: str, cli=DEFAULT_CLI):
    api = client.CoreV1Api(cli)
    pvs = api.list_persistent_volume(label_selector=f'MLAD.PROJECT.APP={name}').items
    for pv in pvs:
        api.delete_persistent_volume(pv.metadata.name)


def _create_pvc(name: str, pv_index: int, pv_mount, namespace: str, cli=DEFAULT_CLI):
    api = client.CoreV1Api(cli)
    pvc_name = f'{name}-{pv_index}-pvc'
    api.create_namespaced_persistent_volume_claim(
        namespace,
        client.V1PersistentVolumeClaim(
            api_version='v1',
            kind='PersistentVolumeClaim',
            metadata=client.V1ObjectMeta(
                name=pvc_name
            ),
            spec=client.V1PersistentVolumeClaimSpec(
                access_modes=['ReadWriteMany'],
                resources=client.V1ResourceRequirements(
                    requests={'storage': '10Gi'}
                ),
                selector=client.V1LabelSelector(
                    match_labels={'mount': f'{name}-{pv_index}'}
                ),
                storage_class_name=''
            )
        )
    )
    return pvc_name


def _create_V1Env(name: str, value: Optional[Union[str, int]] = None, field_path: str = None):
    return client.V1EnvVar(
        name=name,
        value=str(value) if value is not None else None,
        value_from=client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(
                field_path=field_path
            )
        ) if field_path else None
    )


def create_apps(namespace, apps, extra_labels={}, cli=DEFAULT_CLI):
    if not isinstance(namespace, client.models.v1_namespace.V1Namespace):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    namespace_name = namespace.metadata.name
    namespace_spec = inspect_namespace(namespace, cli)
    config_labels = get_config_labels(namespace, 'project-labels', cli)
    namespace_labels = get_labels(namespace)

    image_name = namespace_spec['image']
    project_base = namespace_spec['base']

    RESTART_POLICY_STORE = {
        'never': 'Never',
        'onfailure': 'OnFailure',
        'always': 'Always',
    }

    instances = []
    for name, app in apps.items():
        # Check running already
        if get_apps(namespace_spec['key'], extra_filters={'MLAD.PROJECT.APP': name}, cli=cli):
            raise exceptions.Duplicated('Already running app.')

        kind = app['kind']
        image = app['image'] or image_name
        quota = app['quota']
        app_envs = app['env'] or {}
        app_envs.update({
            'PROJECT': namespace_spec['project'],
            'USERNAME': namespace_spec['username'],
            'PROJECT_KEY': namespace_spec['key'],
            'PROJECT_ID': str(namespace_spec['id']),
            'APP': name,
            'PYTHONUNBUFFERED': 1
        })
        config_envs = utils.decode_dict(config_labels['MLAD.PROJECT.ENV'])
        config_envs = {env.split('=', 1)[0]: env.split('=', 1)[1] for env in config_envs}
        app_envs.update(config_envs)
        if quota is not None and quota['gpu'] == 0:
            app_envs.update({'NVIDIA_VISIBLE_DEVICES': 'none'})
        envs = [_create_V1Env(k, v) for k, v in app_envs.items()]
        envs.append(_create_V1Env('POD_NAME', field_path='metadata.name'))

        command = app['command'] or []
        args = app['args'] or []
        if isinstance(command, str):
            command = command.split()
        if isinstance(args, str):
            args = args.split()
        command += args

        labels = copy.copy(namespace_labels) or {}
        labels.update(extra_labels)
        labels['MLAD.PROJECT.APP'] = name

        constraints = app['constraints']
        pv_mounts = app['mounts'] or []
        v_mounts = ['/etc/timezone:/etc/timezone:ro', '/etc/localtime:/etc/localtime:ro']

        config_labels['MLAD.PROJECT.APP'] = name
        config_labels['MLAD.PROJECT.APP.KIND'] = kind

        # Secrets
        secrets = f"{project_base}-auth"

        restart_policy = RESTART_POLICY_STORE.get(app['restartPolicy'].lower(), 'Never')
        init_containers = None
        if app['depends'] is not None:
            init_containers = [_depends_to_init_container(app['depends'], envs)]

        try:
            pvc_specs = []
            for pv_index, pv_mount in enumerate(pv_mounts):
                _create_pv(name, pv_index, pv_mount)
                pvc_specs.append({
                    'name': _create_pvc(name, pv_index, pv_mount, namespace_name),
                    'mountPath': pv_mount['mountPath']
                })

            if kind == 'Job':
                ret = _create_job(name, image, command, namespace_name, restart_policy, envs, v_mounts, pvc_specs,
                                  1, None, quota, None, init_containers, labels, constraints, secrets, cli)
            elif kind == 'Service':
                scale = app['scale']
                ret = _create_deployment(name, image, command, namespace_name, envs, v_mounts, pvc_specs, scale,
                                         quota, None, init_containers, labels, constraints, secrets, cli)
            else:
                raise DeprecatedError
            instances.append(ret)

            ingress_specs = []
            if app['expose'] is not None:
                ports = set([expose['port'] for expose in app['expose']])
                api.create_namespaced_service(namespace_name, client.V1Service(
                    metadata=client.V1ObjectMeta(
                        name=name,
                        labels=labels
                    ),
                    spec=client.V1ServiceSpec(
                        selector={'MLAD.PROJECT.APP': name},
                        ports=[client.V1ServicePort(port=port, name=f'port{port}')
                               for port in ports]
                    )
                ))
                for expose in app['expose']:
                    port = expose['port']
                    ingress = expose['ingress']
                    if ingress is not None:
                        ingress = expose['ingress']
                        path = ingress['path']
                        rewrite_path = ingress['rewritePath']
                        ingress_name = f'{name}-ingress-{port}'
                        ingress_path = path if path is not None else \
                            f"/{namespace_spec['username']}/{namespace_spec['name']}/{name}"
                        ingress_specs.append({'port': port, 'path': ingress_path})
                        create_ingress(cli, namespace_name, name, ingress_name, port,
                                       ingress_path, rewrite_path)
            config_labels['MLAD.PROJECT.INGRESS'] = json.dumps(ingress_specs)
            create_config_labels(cli, f'app-{name}-labels', namespace_name, config_labels)
        except ApiException as e:
            msg, status = exceptions.handle_k8s_api_error(e)
            err_msg = f'Failed to create apps: {msg}'
            raise exceptions.APIError(err_msg, status)
    return instances


def update_apps(namespace, update_yaml, update_specs, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not a valid type.')
    if not isinstance(namespace, client.models.v1_namespace.V1Namespace):
        raise TypeError('Parameter is not a valid type.')
    results = []
    for update_spec in update_specs:
        update_spec = update_spec.dict()
        app_name = update_spec['name']
        if update_yaml['app'][app_name]['kind'] == 'Service':
            results.append(_update_k8s_deployment(cli, namespace, update_spec))
        else:
            results.append(_update_k8s_job(cli, namespace, update_spec))
    return results


def _update_k8s_deployment(cli, namespace, update_spec):
    app_name = update_spec['name']
    scale = update_spec['scale']
    command = update_spec['command'] or []
    args = update_spec['args'] or []
    quota = update_spec['quota'] or {}
    namespace_name = namespace.metadata.name

    resources = _resources_to_V1Resource(resources=quota).to_dict()

    if isinstance(command, str):
        command = command.split()
    if isinstance(args, str):
        args = args.split()
    command += args

    def _body(option: str, value: str, spec: str = "container"):
        if spec == "container":
            path = f"/spec/template/spec/containers/0/{option}"
        elif spec == "deployment":
            path = f"/spec/{option}"
        elif spec == "metadata":
            path = f"/metadata/{option}"
        return {"op": "replace", "path": path, "value": value}

    # update
    body = []
    body.append(_body("replicas", scale, "deployment"))
    body.append(_body("command", command))

    for resource in resources:
        body.append(_body(f"resources/{resource}", resources[resource]))

    if update_spec['image'] is not None:
        body.append(_body("image", update_spec['image']))
    else:
        namespace_spec = inspect_namespace(namespace, cli)
        body.append(_body("image", namespace_spec['image']))

    # update env
    deployment = get_deployment(app_name, namespace_name, cli)
    container_spec = deployment.spec.template.spec.containers[0]
    current = {env.name: env.value for env in container_spec.env}
    for key in list(update_spec['env']['current'].keys()):
        if key not in config_envs:
            current.pop(key)
    for key in list(update_spec['env']['update'].keys()):
        if key in config_envs:
            update_spec['env']['update'].pop(key)
    current.update(update_spec['env']['update'])
    envs = [_create_V1Env(k, v).to_dict() for k, v in current.items()]
    body.append(_body("env", envs))

    try:
        cause = {"kubernetes.io/change-cause": f"MLAD:{update_spec}"}
        body.append(_body("annotations", cause, "metadata"))
        api = client.AppsV1Api(cli)
        return api.patch_namespaced_deployment(app_name, namespace_name, body=body)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        err_msg = f'Failed to update apps: {msg}'
        raise exceptions.APIError(err_msg, status)


def _update_k8s_job(cli, namespace, update_spec):
    app_name = update_spec['name']
    image = update_spec['image']
    command = update_spec['command'] or []
    args = update_spec['args'] or []
    quota = update_spec['quota'] or {}
    namespace_name = namespace.metadata.name

    resources = _resources_to_V1Resource(resources=quota)

    if isinstance(command, str):
        command = command.split()
    if isinstance(args, str):
        args = args.split()
    command += args

    k8s_job = get_app_from_kind(cli, app_name, namespace_name, 'Job')
    # remove invalid properties to re-run the job
    k8s_job.metadata = client.V1ObjectMeta(name=k8s_job.metadata.name, labels=k8s_job.metadata.labels)
    k8s_job.spec.selector = None
    del k8s_job.spec.template.metadata.labels['controller-uid']

    container_spec = k8s_job.spec.template.spec.containers[0]
    current = {env.name: env.value for env in container_spec.env}
    for key in list(update_spec['env']['current'].keys()):
        if key not in config_envs:
            current.pop(key)
    for key in list(update_spec['env']['update'].keys()):
        if key in config_envs:
            update_spec['env']['update'].pop(key)
    current.update(update_spec['env']['update'])
    env = [client.V1EnvVar(name=k, value=v).to_dict() for k, v in current.items()]

    container_spec.command = command
    container_spec.resources = resources
    if image is not None:
        container_spec.image = image
    else:
        namespace_spec = inspect_namespace(namespace, cli)
        container_spec.image = namespace_spec['image']

    container_spec.env = env
    try:
        api = client.BatchV1Api(cli)
        api.delete_namespaced_job(app_name, namespace_name, propagation_policy='Foreground')
        w = watch.Watch()
        for event in w.stream(
                func=api.list_namespaced_job,
                namespace=namespace_name,
                field_selector=f'metadata.name={app_name}',
                timeout_seconds=180):
            if event['type'] == 'DELETED':
                w.stop()
        return api.create_namespaced_job(namespace_name, body=k8s_job)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        err_msg = f'Failed to update apps: {msg}'
        raise exceptions.APIError(err_msg, status)


def _delete_job(cli, name, namespace):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.BatchV1Api(cli)
    return api.delete_namespaced_job(name, namespace, propagation_policy='Foreground')


def _delete_deployment(cli, name, namespace):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.AppsV1Api(cli)
    return api.delete_namespaced_deployment(name, namespace, propagation_policy='Foreground')


def remove_apps(apps, namespace,
                disconnect_handler=None, timeout=0xFFFF, stream=False, cli=DEFAULT_CLI):
    api = client.CoreV1Api(cli)
    network_api = client.NetworkingV1Api(cli)

    def _get_app_spec(app):
        spec = inspect_app(app, cli)
        app_name = spec['name']
        task_keys = list(spec['tasks'].keys())

        config_labels = get_config_labels(namespace, f'app-{app_name}-labels', cli)
        kind = config_labels['MLAD.PROJECT.APP.KIND']
        return app_name, kind, task_keys

    app_specs = [_get_app_spec(app) for app in apps]
    # For check app deleted
    collector = Collector()
    monitor = DelMonitor(cli, collector, app_specs, namespace)
    monitor.start()

    if disconnect_handler is not None:
        disconnect_handler.add_callback(lambda: monitor.stop())

    for spec in app_specs:
        app_name, kind, _ = spec
        try:
            _delete_pvs(app_name)
            if kind == 'Job':
                _delete_job(cli, app_name, namespace)
            elif kind == 'Service':
                _delete_deployment(cli, app_name, namespace)

            if get_app_service(cli, namespace, app_name) is not None:
                api.delete_namespaced_service(app_name, namespace)

            ingress_list = network_api.list_namespaced_ingress(
                namespace, label_selector=f'MLAD.PROJECT.APP={app_name}').items
            if len(ingress_list) > 0:
                ingress_name = ingress_list[0].metadata.name
                network_api.delete_namespaced_ingress(ingress_name, namespace)
        except ApiException as e:
            print("Exception when calling ExtensionsV1beta1Api->delete_namespaced_ingress: %s\n" % e)

    def resp_from_collector(collector):
        for _ in collector:
            yield _

    if stream:
        return resp_from_collector(collector)
    else:
        removed = False
        for app in apps:
            app_removed = False
            name, kind, _ = _get_app_spec(app)
            if not get_app_from_kind(cli, name, namespace, kind) and \
                    not get_app(name, namespace, cli):
                app_removed = True
            else:
                app_removed = False
                removed &= app_removed
        return (removed, (_ for _ in resp_from_collector(collector)))


def get_nodes(cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')

    api = client.CoreV1Api(cli)
    return {node.metadata.name: node for node in api.list_node().items}


def inspect_node(node):
    if not isinstance(node, client.models.v1_node.V1Node):
        raise TypeError('Parameter is not valid type.')
    hostname = node.metadata.labels['kubernetes.io/hostname']
    availability = 'active' if node.spec.taints is None else 'pause'
    platform = node.metadata.labels['kubernetes.io/os']
    arch = node.metadata.labels['kubernetes.io/arch']
    resources = node.status.capacity
    engine_version = node.status.node_info.kubelet_version
    role = [_.split('/')[-1] for _ in node.metadata.labels if _.startswith('node-role')]
    state = node.status.conditions[-1].type
    addr = node.status.addresses[0].address
    labels = dict([(_, node.metadata.labels[_]) for _ in node.metadata.labels if 'kubernetes.io/' not in _])

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
        'status': {'State': state, 'Addr': addr},
    }


def enable_node(node_name, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    api = client.CoreV1Api(cli)
    body = {
        "spec": {"taints": None}
    }
    try:
        api.patch_node(node_name, body)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find node {node_name}.')
        else:
            raise exceptions.APIError(msg, status)


def disable_node(node_name, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')

    api = client.CoreV1Api(cli)
    body = {
        "spec": {"taints": [{"effect": "NoSchedule",
                            "key": "node-role.kubernetes.io/worker"}]}
    }
    try:
        api.patch_node(node_name, body)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find node {node_name}.')
        else:
            raise exceptions.APIError(msg, status)


def delete_node(node_name, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not a valid type.')
    api = client.CoreV1Api(cli)
    try:
        api.delete_node(node_name)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find node {node_name}.')
        else:
            raise exceptions.APIError(msg, status)


def add_node_labels(node_name, cli=DEFAULT_CLI, **kv):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')

    api = client.CoreV1Api(cli)
    body = {
        "metadata": {
            "labels": dict()
        }
    }
    for key in kv:
        body['metadata']['labels'][key] = kv[key]
    try:
        api.patch_node(node_name, body)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find node {node_name}.')
        else:
            raise exceptions.APIError(msg, status)


def remove_node_labels(node_name, cli=DEFAULT_CLI, *keys):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')

    api = client.CoreV1Api(cli)
    body = {
        "metadata": {
            "labels": dict()
        }
    }
    for key in keys:
        body['metadata']['labels'][key] = None
    try:
        api.patch_node(node_name, body)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find node {node_name}.')
        else:
            raise exceptions.APIError(msg, status)


def scale_app(app, scale_spec, cli=DEFAULT_CLI):
    if not isinstance(cli, client.api_client.ApiClient):
        raise TypeError('Parameter is not valid type.')
    if not isinstance(app, client.models.v1_deployment.V1Deployment):
        raise TypeError('Target app is not a deployment object.')
    name = app.metadata.name
    namespace = app.metadata.namespace
    api = client.AppsV1Api(cli)
    body = {
        "spec": {
            "replicas": scale_spec
        }
    }
    ret = api.patch_namespaced_deployment_scale(
        name=name, namespace=namespace, body=body)
    return ret


def container_logs(cli, project_key, tail='all', follow=False, timestamps=False):
    instances = cli.containers.list(all=True, filters={'label': f'MLAD.PROJECT={project_key}'})
    logs = [(
        inst.attrs['Config']['Labels']['MLAD.PROJECT.APP'],
        inst.logs(follow=follow, tail=tail, timestamps=timestamps, stream=True)) for inst in instances]
    if len(logs):
        with LogCollector() as collector:
            for name, log in logs:
                collector.add_iterable(log, name=name, timestamps=timestamps)
            for message in collector:
                yield message
    else:
        print('Cannot find running containers.', file=sys.stderr)


def get_app_with_names_or_ids(project_key, names_or_ids=[], cli=DEFAULT_CLI):
    # get running apps with app or pod name
    api = client.CoreV1Api(cli)
    apps = get_apps(project_key, cli=cli)
    namespace = get_namespace(cli, project_key=project_key).metadata.name

    selected = []
    sources = [(_['name'], list(_['tasks'].keys())) for _ in
               [inspect_app(_, cli) for _ in apps.values()]]
    if names_or_ids:
        selected = []
        for _ in sources:
            if _[0] in names_or_ids:
                selected += [(_[0], __) for __ in _[1]]
                names_or_ids.remove(_[0])
            else:
                # check task ids of svc
                for __ in _[1]:
                    if __ in names_or_ids:
                        selected += [(_[0], __)]
                        names_or_ids.remove(__)
        if names_or_ids:
            raise exceptions.NotFound(f"Cannot find name or task in project: {', '.join(names_or_ids)}")

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

    if not targets:
        raise exceptions.NotFound("Cannot find running apps")

    return targets


def get_project_logs(project_key, tail='all', follow=False, timestamps=False,
                     selected=False, disconnect_handler=None, targets=[], cli=DEFAULT_CLI):
    get_apps(project_key, cli=cli)
    namespace = get_namespace(cli, project_key=project_key).metadata.name

    handler = LogHandler(cli)

    logs = [(target, handler.logs(namespace, target, details=True, follow=follow,
                                  tail=tail, timestamps=timestamps, stdout=True, stderr=True))
            for app_name, target in targets]

    if len(logs):
        with LogCollector() as collector:
            for name, log in logs:
                collector.add_iterable(log, name=name, timestamps=timestamps)
            # Register Disconnect Callback
            if disconnect_handler:
                disconnect_handler.add_callback(lambda: handler.close())
            if follow and not selected:
                last_resource = None
                monitor = LogMonitor(cli, handler, collector, namespace, last_resource=last_resource,
                                     follow=follow, tail=tail, timestamps=timestamps)
                monitor.start()
                if disconnect_handler:
                    disconnect_handler.add_callback(lambda: monitor.stop())
            yield from collector
    else:
        print('Cannot find running containers.', file=sys.stderr)


def create_ingress(cli, namespace, app_name, ingress_name, port, base_path='/', rewrite=False):
    api = client.NetworkingV1Api(cli)
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
    body = client.V1Ingress(
        api_version="networking.k8s.io/v1",
        kind="Ingress",
        metadata=client.V1ObjectMeta(name=ingress_name, annotations=annotations,
                                     labels={'MLAD.PROJECT.APP': app_name}),
        spec=client.V1IngressSpec(
            rules=[
                client.V1IngressRule(
                    http=client.V1HTTPIngressRuleValue(
                        paths=[client.V1HTTPIngressPath(
                            path=f"{base_path}(/|$)(.*)" if rewrite else base_path,
                            path_type='ImplementationSpecific',
                            backend=client.V1IngressBackend(
                                service=client.V1IngressServiceBackend(
                                    name=app_name,
                                    port=client.V1ServiceBackendPort(
                                        number=port
                                    )
                                )
                            )
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


def check_ingress(ingress_name, namespace, cli=DEFAULT_CLI):
    w = watch.Watch()
    api = client.NetworkingV1Api(cli)
    try:
        res = api.read_namespaced_ingress(ingress_name, namespace)
        status = res.status.load_balancer.ingress
        if status is not None:
            return True
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find ingress "{ingress_name}" in "{namespace}".')
    for event in w.stream(func=api.list_namespaced_ingress,
                          namespace=namespace,
                          field_selector=f'metadata.name={ingress_name}',
                          timeout_seconds=60):
        if event['type'] == 'MODIFIED':
            status = event['object'].status.load_balancer.ingress
            if status is not None:
                return True
    return False


def delete_ingress(cli, namespace, ingress_name):
    api = client.NetworkingV1Api(cli)
    return api.delete_namespaced_ingress(ingress_name, namespace)


def parse_mem(str_mem):
    if str_mem.endswith('Ki'):
        mem = float(str_mem[:-2]) / 1024
    elif str_mem.endswith('Mi'):
        mem = float(str_mem[:-2])
    elif str_mem.endswith('Gi'):
        mem = float(str_mem[:-2]) * 1024
    else:
        # TODO Other units may need to be considered
        try:
            mem = float(str_mem)
        except ValueError:
            raise InvalidMetricUnitError('mem', str_mem)
    return mem


def parse_cpu(str_cpu):
    if str_cpu.endswith('n'):
        cpu = float(str_cpu[:-1]) / 1e9
    elif str_cpu.endswith('m'):
        cpu = float(str_cpu[:-1]) / 1e3
    else:
        # TODO Other units may need to be considered
        try:
            cpu = float(str_cpu)
        except ValueError:
            raise InvalidMetricUnitError('cpu', str_cpu)
    return cpu


def get_node_resources(node, no_trunc, cli=DEFAULT_CLI):
    api = client.CustomObjectsApi(cli)
    v1_api = client.CoreV1Api(cli)
    name = node.metadata.name

    allocatable = node.status.allocatable
    mem = parse_mem(allocatable['memory'])
    cpu = int(allocatable['cpu'])
    gpu = int(allocatable['nvidia.com/gpu']) if 'nvidia.com/gpu' in allocatable else 0

    try:
        metric = api.get_cluster_custom_object("metrics.k8s.io", "v1beta1", "nodes", name)
        try:
            used_mem = parse_mem(metric['usage']['memory'])
        except InvalidMetricUnitError as e:
            print(f'Node "{name}": {e}')
            used_mem = 'UnitError'
        try:
            used_cpu = parse_cpu(metric['usage']['cpu'])
        except InvalidMetricUnitError as e:
            print(f'Node "{name}": {e}')
            used_cpu = 'UnitError'
    except ApiException as e:
        if e.headers['Content-Type'] == 'application/json':
            body = json.loads(e.body)
            if body['kind'] == 'Status':
                print(f"{body['status']} : {body['message']}")
            used_mem = 'NotReady'
            used_cpu = 'NotReady'
        elif e.status == 404 or e.status == 503:
            print('Metrics server unavailable.')
            used_mem = '-'
            used_cpu = '-'

    used_gpu = 0
    selector = (f'spec.nodeName={name},status.phase!=Succeeded,status.phase!=Failed')
    pods = v1_api.list_pod_for_all_namespaces(field_selector=selector)
    for pod in pods.items:
        for container in pod.spec.containers:
            requests = defaultdict(lambda: '0', container.resources.requests or {})
            used_gpu += int(requests['nvidia.com/gpu'])

    res = {
        'mem': {'capacity': mem, 'used': used_mem,
                'allocatable': mem - used_mem if not isinstance(used_mem, str) else '-'},
        'cpu': {'capacity': cpu, 'used': used_cpu,
                'allocatable': cpu - used_cpu if not isinstance(used_cpu, str) else '-'},
        'gpu': {'capacity': gpu, 'used': used_gpu, 'allocatable': gpu - used_gpu},
    }

    if not no_trunc:
        for resource, value in res.items():
            for k in value:
                if not isinstance(res[resource][k], str):
                    res[resource][k] = round(res[resource][k], 1)

    return res


def get_project_resources(project_key: str, group_by: str = 'project', no_trunc: bool = True,
                          cli=DEFAULT_CLI):
    api = client.CustomObjectsApi(cli)
    v1_api = client.CoreV1Api(cli)
    res = {}
    apps = get_apps(project_key, cli=cli)

    def parse_gpu(pod):
        used = None
        for container in pod.spec.containers:
            requests = defaultdict(lambda: None, container.resources.requests or {})
            gpu = requests['nvidia.com/gpu']
            if gpu is not None:
                if used is None:
                    used = 0
                used += int(gpu)
        return used

    project_res = {'cpu': 0, 'gpu': 0, 'mem': 0}
    cpu_unit_error = False
    mem_unit_error = False
    for name, app in apps.items():
        res[name] = {}
        namespace = app.metadata.namespace

        pods = v1_api.list_namespaced_pod(namespace,
                                          label_selector=f'MLAD.PROJECT.APP={name}')
        for pod in pods.items:
            resource = {'mem': 0, 'cpu': 0, 'gpu': 0}
            pod_name = pod.metadata.name
            try:
                metric = api.get_namespaced_custom_object("metrics.k8s.io", "v1beta1", namespace,
                                                          "pods", pod_name)
                for _ in metric['containers']:
                    try:
                        resource['cpu'] += parse_cpu(_['usage']['cpu'])
                    except InvalidMetricUnitError as e:
                        print(f'Pod "{pod_name}": {e}')
                        resource['cpu'] = 'UnitError'
                        cpu_unit_error = True
                    try:
                        resource['mem'] += parse_mem(_['usage']['memory'])
                    except InvalidMetricUnitError as e:
                        print(f'Pod "{pod_name}": {e}')
                        resource['mem'] = 'UnitError'
                        mem_unit_error = True

                pod_gpu_usage = parse_gpu(pod)
                if pod_gpu_usage is not None:
                    resource['gpu'] += pod_gpu_usage

                if group_by == 'project':
                    for k in project_res:
                        project_res[k] += resource[k] if not isinstance(resource[k], str) else 0

                if not no_trunc:
                    for k in resource:
                        resource[k] = round(resource[k], 1) if not isinstance(resource[k], str) \
                            else resource[k]

                res[name][pod_name] = resource

            except ApiException as e:
                if e.headers['Content-Type'] == 'application/json':
                    body = json.loads(e.body)
                    if body['kind'] == 'Status':
                        print(f"{body['status']} : {body['message']}")
                    res[name][pod_name] = {'mem': 'NotReady', 'cpu': 'NotReady', 'gpu': 'NotReady'}
                elif e.status == 404 or e.status == 503:
                    print('Metrics server unavailable.')
                    res[name][pod_name] = {'mem': '-', 'cpu': '-', 'gpu': '-'}
                continue

    if group_by == 'project':
        if cpu_unit_error:
            project_res['cpu'] = 'UnitError'
        if mem_unit_error:
            project_res['mem'] = 'UnitError'

        if not no_trunc:
            for k in project_res:
                project_res[k] = round(project_res[k], 1) if not isinstance(project_res[k], str) \
                    else project_res[k]

        return project_res
    elif group_by == 'app':
        return res
