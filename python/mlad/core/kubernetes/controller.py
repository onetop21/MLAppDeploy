import copy
import time
import json

from multiprocessing.pool import ThreadPool
from typing import Union, List, Dict, Optional, Tuple, Generator, Any
from collections import defaultdict
from pathlib import Path

import jwt

from kubernetes import client, config, watch
from kubernetes.client.api_client import ApiClient
from kubernetes.client.rest import ApiException

from mlad.core import exceptions
from mlad.core.exceptions import (
    InsufficientSessionQuotaError, NamespaceAlreadyExistError,
    DeprecatedError, InvalidAppError, InvalidMetricUnitError,
    ProjectNotFoundError, handle_k8s_exception
)
from mlad.core.libs import utils
from mlad.core.libs.constants import (
    CONFIG_ENVS, MLAD_PROJECT, MLAD_PROJECT_API_VERSION, MLAD_PROJECT_APP, MLAD_PROJECT_APP_KIND, MLAD_PROJECT_BASE,
    MLAD_PROJECT_ENV, MLAD_PROJECT_HOSTNAME, MLAD_PROJECT_IMAGE, MLAD_PROJECT_INGRESS, MLAD_PROJECT_KIND,
    MLAD_PROJECT_NAME, MLAD_PROJECT_NAMESPACE, MLAD_PROJECT_WORKSPACE, MLAD_PROJECT_SESSION,
    MLAD_PROJECT_USERNAME, MLAD_PROJECT_VERSION, MLAD_PROJECT_YAML
)
from mlad.core.kubernetes.monitor import DelMonitor, Collector
from mlad.core.kubernetes.logs import LogHandler, LogCollector, LogMonitor


App = Union[client.V1Job, client.V1Deployment]
LogGenerator = Generator[Dict[str, str], None, None]
LogTuple = Tuple[Dict[str, str]]


def get_contexts(config_file: str = f'{Path.home()}/.kube/config') -> Tuple[List[Union[Dict, List, Any]], Any]:
    return config.list_kube_config_contexts(config_file)


def get_api_client(
    config_file: str = f'{Path.home()}/.kube/config', context: Optional[str] = None,
    validate: bool = True
) -> ApiClient:
    try:
        return config.new_client_from_config(context=context, config_file=config_file)
    except config.config_exception.ConfigException:
        pass
    try:
        config.load_incluster_config()
        # If Need, set configuration parameter from client.Configuration
        return ApiClient()
    except config.config_exception.ConfigException:
        if validate:
            raise exceptions.InvalidKubeConfigError(config_file, context)
        return None


DEFAULT_CLI = get_api_client(validate=False)


def check_project_key(project_key: str, app: App, cli: ApiClient = DEFAULT_CLI) -> bool:
    target_key = inspect_app(app, cli=cli)['key']
    if project_key == target_key:
        return True
    else:
        raise InvalidAppError(project_key, app.metadata.name)


def get_k8s_namespaces(extra_labels: List[str] = [], cli: ApiClient = DEFAULT_CLI) -> List[client.V1Namespace]:
    api = client.CoreV1Api(cli)
    selector = [MLAD_PROJECT] + extra_labels
    resp = api.list_namespace(label_selector=','.join(selector))
    return resp.items


def get_k8s_namespace(project_key: str, cli: ApiClient = DEFAULT_CLI) -> client.V1Namespace:
    api = client.CoreV1Api(cli)
    resp = api.list_namespace(label_selector=f'{MLAD_PROJECT}={project_key}')
    if len(resp.items) == 0:
        raise ProjectNotFoundError(project_key)
    elif len(resp.items) == 1:
        return resp.items[0]
    else:
        raise exceptions.Duplicated(
            "Need to remove namespaces or down project, because exists duplicated namespaces.")


def _get_k8s_config_map_data(namespace: Union[str, client.V1Namespace], key: str, cli: ApiClient = DEFAULT_CLI) -> Dict[str, str]:
    # key='project-labels', 'app-{name}-labels'
    if isinstance(namespace, client.V1Namespace):
        namespace = namespace.metadata.name
    api = client.CoreV1Api(cli)
    resp = api.read_namespaced_config_map(key, namespace)
    return resp.data


def obtain_k8s_config_map(key: str, labels: Dict[str, str]) -> client.V1ConfigMap:
    return client.V1ConfigMap(
        api_version='v1',
        kind='ConfigMap',
        data=labels,
        metadata=client.V1ObjectMeta(name=key, namespace=labels[MLAD_PROJECT_NAMESPACE])
    )


def _create_k8s_config_map(
    key: str, labels: Dict[str, str], cli: ApiClient = DEFAULT_CLI
) -> client.V1ConfigMap:
    namespace = labels[MLAD_PROJECT_NAMESPACE]
    api = client.CoreV1Api(cli)
    return api.create_namespaced_config_map(
        namespace,
        obtain_k8s_config_map(key, labels)
    )


def inspect_k8s_namespace(namespace: client.V1Namespace, cli: ApiClient = DEFAULT_CLI) -> Dict:
    labels = namespace.metadata.labels
    if namespace.metadata.deletion_timestamp:
        return {'deleted': True, 'key': labels[MLAD_PROJECT]}
    config_labels = _get_k8s_config_map_data(namespace, 'project-labels', cli)
    hostname, path = config_labels[MLAD_PROJECT_WORKSPACE].split(':')

    return {
        'key': labels[MLAD_PROJECT],
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': config_labels[MLAD_PROJECT_USERNAME],
        'name': config_labels[MLAD_PROJECT_NAMESPACE],
        'project': labels[MLAD_PROJECT_NAME],
        'version': config_labels[MLAD_PROJECT_VERSION],
        'base': config_labels[MLAD_PROJECT_BASE],
        'image': config_labels[MLAD_PROJECT_IMAGE],
        'kind': config_labels.get(MLAD_PROJECT_KIND, 'Deployment'),
        'created': namespace.metadata.creation_timestamp,
        'project_yaml': (namespace.metadata.annotations or dict()).get(MLAD_PROJECT_YAML, '{}')
    }


def get_project_session(namespace: client.V1Namespace, cli: ApiClient = DEFAULT_CLI) -> str:
    config_labels = _get_k8s_config_map_data(namespace, 'project-labels', cli)
    return config_labels[MLAD_PROJECT_SESSION]


def obtain_k8s_namespace(base_labels: Dict[str, str], project_yaml: Dict) -> client.V1Namespace:
    basename = base_labels[MLAD_PROJECT_BASE]
    namespace_name = f"{basename}-cluster"
    keys = {
        MLAD_PROJECT_API_VERSION: base_labels[MLAD_PROJECT_API_VERSION],
        MLAD_PROJECT: base_labels[MLAD_PROJECT],
        MLAD_PROJECT_NAME: base_labels[MLAD_PROJECT_NAME],
        MLAD_PROJECT_USERNAME: base_labels[MLAD_PROJECT_USERNAME],
        MLAD_PROJECT_HOSTNAME: base_labels[MLAD_PROJECT_HOSTNAME]
    }
    annotations = {
        MLAD_PROJECT_YAML: json.dumps(project_yaml)
    }
    return client.V1Namespace(
        api_version='v1',
        kind='Namespace',
        metadata=client.V1ObjectMeta(
            name=namespace_name,
            labels=keys,
            annotations=annotations
        )
    )


def obtain_docker_k8s_secret(base_labels: Dict[str, str], credential: str):
    basename = base_labels[MLAD_PROJECT_BASE]
    namespace = base_labels[MLAD_PROJECT_NAMESPACE]
    return client.V1Secret(
        api_version='v1',
        kind='Secret',
        metadata=client.V1ObjectMeta(name=f"{basename}-auth", namespace=namespace),
        type='kubernetes.io/dockerconfigjson',
        data={'.dockerconfigjson': credential}
    )


def create_k8s_namespace_with_data(
    base_labels: Dict[str, str],
    project_yaml: Dict, credential: str, cli: ApiClient = DEFAULT_CLI
) -> LogGenerator:
    api = client.CoreV1Api(cli)
    project_key = base_labels[MLAD_PROJECT]
    try:
        get_k8s_namespace(project_key, cli=cli)
    except ProjectNotFoundError:
        pass
    else:
        raise NamespaceAlreadyExistError(project_key)
    namespace_name = base_labels[MLAD_PROJECT_NAMESPACE]
    message = f"Create a namespace [{namespace_name}]...\n"
    yield {'stream': message}
    try:
        api.create_namespace(
            obtain_k8s_namespace(base_labels, project_yaml)
        )
        _create_k8s_config_map('project-labels', base_labels, cli=cli)

        # AuthConfig
        api.create_namespaced_secret(
            namespace_name,
            obtain_docker_k8s_secret(base_labels, credential)
        )
    except ApiException as e:
        message = f"Failed to create namespace.\n{e}\n"
        yield {'result': 'failed', 'stream': message}


def delete_k8s_namespace(
    namespace: client.V1Namespace, timeout: int = 0xFFFF,
    cli: ApiClient = DEFAULT_CLI
) -> LogGenerator:
    api = client.CoreV1Api(cli)
    spec = inspect_k8s_namespace(namespace, cli)
    api.delete_namespace(namespace.metadata.name)

    removed = False
    for tick in range(timeout):
        try:
            get_k8s_namespace(spec['key'], cli=cli)
        except ProjectNotFoundError:
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


def update_k8s_namespace(
    namespace: client.V1Namespace, update_yaml: Dict, cli: ApiClient = DEFAULT_CLI
) -> client.V1Namespace:
    api = client.CoreV1Api(cli)
    name = namespace.metadata.name
    namespace.metadata.annotations[MLAD_PROJECT_YAML] = json.dumps(update_yaml)
    try:
        return api.patch_namespace(name, namespace)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find namespace {name}.')
        else:
            raise exceptions.APIError(msg, status)


@handle_k8s_exception('deployment', namespaced=True)
def get_k8s_deployment(name: str, namespace: str, cli: ApiClient = DEFAULT_CLI) -> client.V1Deployment:
    api = client.AppsV1Api(cli)
    return api.read_namespaced_deployment(name, namespace)


@handle_k8s_exception('daemonset', namespaced=True)
def get_k8s_daemonset(name: str, namespace: str, cli: ApiClient = DEFAULT_CLI) -> client.V1DaemonSet:
    api = client.AppsV1Api(cli)
    return api.read_namespaced_daemon_set(name, namespace)


def get_app(name: str, namespace: str, cli: ApiClient = DEFAULT_CLI) -> App:
    key = f'app-{name}-labels'
    config_labels = _get_k8s_config_map_data(namespace, key, cli)
    kind = config_labels[MLAD_PROJECT_APP_KIND]
    name = config_labels[MLAD_PROJECT_APP]
    app = get_app_from_kind(name, namespace, kind, cli=cli)
    return app


def get_apps(project_key: Optional[str] = None,
             extra_filters: Dict[str, str] = {},
             cli: ApiClient = DEFAULT_CLI) -> List[App]:
    batch_api = client.BatchV1Api(cli)
    apps_api = client.AppsV1Api(cli)
    filters = [f'{MLAD_PROJECT}={project_key}' if project_key else MLAD_PROJECT]
    filters += [f'{key}={value}' for key, value in extra_filters.items()]

    apps = []
    apps += batch_api.list_job_for_all_namespaces(label_selector=','.join(filters)).items
    apps += apps_api.list_deployment_for_all_namespaces(label_selector=','.join(filters)).items
    return apps


@handle_k8s_exception('service', namespaced=True)
def get_k8s_service(name: str, namespace: str, cli: ApiClient = DEFAULT_CLI) -> client.V1Service:
    api = client.CoreV1Api(cli)
    return api.read_namespaced_service(name, namespace)


def get_k8s_service_of_app(namespace: str, app_name: str, cli: ApiClient = DEFAULT_CLI) -> Optional[client.V1Service]:
    api = client.CoreV1Api(cli)
    service = api.list_namespaced_service(
        namespace, label_selector=f"{MLAD_PROJECT_APP}={app_name}")
    if len(service.items) == 0:
        return None
    elif len(service.items) == 1:
        return service.items[0]


def get_app_from_kind(app_name: str, namespace: str, kind: str, cli: ApiClient = DEFAULT_CLI) -> Optional[App]:
    if kind == 'Job':
        batch_api = client.BatchV1Api(cli)
        resp = batch_api.list_namespaced_job(
            namespace, label_selector=f"{MLAD_PROJECT_APP}={app_name}")
    elif kind == 'Service':
        apps_api = client.AppsV1Api(cli)
        resp = apps_api.list_namespaced_deployment(
            namespace, label_selector=f"{MLAD_PROJECT_APP}={app_name}")
    if len(resp.items) == 0:
        return None
    elif len(resp.items) == 1:
        return resp.items[0]
    else:
        raise exceptions.Duplicated(f"Duplicated {kind} exists in namespace {namespace}")


def get_pod_events(pod: client.V1Pod, cli: ApiClient = DEFAULT_CLI) -> List[Dict[str, str]]:
    api = client.CoreV1Api(cli)

    name = pod.metadata.name
    namespace = pod.metadata.namespace

    events = api.list_namespaced_event(namespace, field_selector='type=Warning').items
    return [{'name': name, 'message': e.message, 'datetime': e.metadata.creation_timestamp}
            for e in events if e.involved_object.name == name]


def get_pod_info(pod: client.V1Pod, cli: ApiClient = DEFAULT_CLI) -> Dict:
    pod_info = {
        'name': pod.metadata.name,
        'namespace': pod.metadata.namespace,
        'created': pod.metadata.creation_timestamp,
        'container_status': list(),
        'status': dict(),
        'node': pod.spec.node_name,
        # Pending, Running, Succeeded, Failed, Unknown
        'phase': pod.status.phase,
        'events': get_pod_events(pod, cli),
        'restart': 0
    }

    def _get_status(container_state: client.V1ContainerState) -> Dict:
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

    def _parse_status(containers: List[Dict]) -> str:
        container = containers[0]
        container_status = container['status']
        state = container_status['state']
        reason = 'Running' if state == 'Running' else \
            container_status['detail']['reason']
        return reason

    if pod.status.container_statuses is not None:
        for container in pod.status.container_statuses:
            container_info = {
                'container_id': container.container_id,
                'restart': container.restart_count,
                'status': _get_status(container.state),
                'ready': container.ready
            }
            pod_info['container_status'].append(container_info)
            pod_info['restart'] += container_info['restart']
        pod_info['status'] = _parse_status(pod_info['container_status'])
    else:
        pod_info['status'] = pod.status.conditions[0].reason if pod.status.conditions \
            else pod.status.reason
    return pod_info


def inspect_app(app: App, cli: ApiClient = DEFAULT_CLI) -> Dict:
    if isinstance(app, client.V1Deployment):
        kind = 'Service'
    elif isinstance(app, client.V1Job):
        kind = 'Job'
    else:
        raise TypeError('Parameter is not a valid type.')

    api = client.CoreV1Api(cli)

    name = app.metadata.name
    namespace = app.metadata.namespace
    config_labels = _get_k8s_config_map_data(namespace, f'app-{name}-labels', cli)

    pods = api.list_namespaced_pod(namespace, label_selector=f'{MLAD_PROJECT_APP}={name}').items

    hostname, path = config_labels.get(MLAD_PROJECT_WORKSPACE, ':').split(':')
    pod_spec = app.spec.template.spec
    service = get_k8s_service_of_app(namespace, name, cli=cli)

    spec = {
        'key': config_labels[MLAD_PROJECT] if config_labels.get(
            MLAD_PROJECT) else '',
        'workspace': {
            'hostname': hostname,
            'path': path
        },
        'username': config_labels.get(MLAD_PROJECT_USERNAME),
        'namespace': config_labels.get(MLAD_PROJECT_NAMESPACE),
        'project': config_labels.get(MLAD_PROJECT_NAME),
        'version': config_labels.get(MLAD_PROJECT_VERSION),
        'base': config_labels.get(MLAD_PROJECT_BASE),
        # Replace from labels['MLAD.PROJECT.IMAGE']
        'image': pod_spec.containers[0].image,
        'env': [{'name': e.name, 'value': e.value} for e in pod_spec.containers[0].env],
        'id': app.metadata.uid,
        'name': config_labels.get(MLAD_PROJECT_APP),
        'replicas': app.spec.parallelism if kind == 'Job' else app.spec.replicas,
        'task_dict': {pod.metadata.name: get_pod_info(pod, cli) for pod in pods},
        'expose': _obtain_app_expose(service, config_labels),
        'created': app.metadata.creation_timestamp,
        'kind': config_labels.get(MLAD_PROJECT_APP_KIND),
    }
    return spec


def _obtain_app_expose(service: Optional[client.V1Service], config_labels: Dict[str, str]) -> List[Dict]:
    if service is None:
        return []
    expose_dict = {str(spec.port): {'port': spec.port} for spec in service.spec.ports}
    try:
        ingresses = json.loads(config_labels.get('MLAD.PROJECT.INGRESS', '[]'))
    except json.decoder.JSONDecodeError:
        ingresses = []
    for ingress in ingresses:
        ingress_port = str(ingress['port'])
        if ingress_port in expose_dict:
            expose_dict[ingress_port]['ingress'] = {'path': ingress['path']}
    return list(expose_dict.values())


def inspect_apps(apps: List[App], cli: ApiClient = DEFAULT_CLI) -> List[Dict]:
    if not apps:
        return []

    results = []
    with ThreadPool(len(apps)) as pool:
        for app in apps:
            results.append(pool.apply_async(inspect_app, (app, cli)))
        return [result.get() for result in results]


def _convert_mounts_to_k8s_volume(
    name: str, mounts: List[str], pvc_specs: List[Dict[str, str]]
) -> Tuple[List[client.V1VolumeMount], List[client.V1Volume]]:
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
        read_only = pvc_spec['readOnly']
        volume_name = f'{name}-vol'
        _mounts.append(
            client.V1VolumeMount(
                name=volume_name,
                mount_path=mount_path,
                read_only=read_only
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


def _convert_quota_to_k8s_resource(
    type: str = 'Quota', resources: Optional[Dict] = None
) -> client.V1ResourceRequirements:
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


def _convert_constraints_to_k8s_node_selector(constraints: Dict) -> Dict[str, str]:
    selector = {}
    if constraints is None:
        return selector
    for k, v in constraints.items():
        if k == 'hostname':
            if v is not None:
                selector["kubernetes.io/hostname"] = v
        elif k == 'label' and v is not None:
            label_dict: Dict = v
            for label_key, label in label_dict.items():
                selector[label_key] = str(label)
    return selector


def _convert_depends_to_k8s_init_container(
    depends: Dict, envs: List[client.V1EnvVar]
) -> client.V1Container:
    env = [*envs, _create_k8s_env('DEPENDENCY_SPECS', json.dumps(depends))]
    return client.V1Container(
        name='dependency-check-container',
        image='ghcr.io/onetop21/mlappdeploy/api-server:dev',
        image_pull_policy='Always',
        command=['python', '-m', 'mlad.core.dependency'],
        env=env
    )


def _obtain_k8s_job(
    name: str, image: str, command: List[str], namespace: str = 'default',
    restart_policy: str = 'Never', envs: List[client.V1EnvVar] = [], mounts: List[str] = [],
    pvc_specs: List[Dict] = [], parallelism: int = 1, completions: int = 1,
    quota: Optional[Dict[str, str]] = None, resources: Optional[Dict] = None,
    init_containers: List[client.V1Container] = [], labels: Optional[Dict[str, str]] = None,
    constraints: Optional[Dict] = None, secrets: str = ''
) -> client.V1Job:

    _resources = _convert_quota_to_k8s_resource(type='Resources', resources=resources) if resources \
        else _convert_quota_to_k8s_resource(resources=quota)

    node_selector = _convert_constraints_to_k8s_node_selector(constraints)

    _mounts, _volumes = _convert_mounts_to_k8s_volume(name, mounts, pvc_specs)

    return client.V1Job(
        api_version='batch/v1',
        kind='Job',
        metadata=client.V1ObjectMeta(name=name, labels=labels, namespace=namespace),
        spec=client.V1JobSpec(
            backoff_limit=0,
            parallelism=parallelism,
            completions=completions,
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
                    node_selector=node_selector,
                    image_pull_secrets=[client.V1LocalObjectReference(name=secrets)]
                    if secrets else None
                )
            )
        )
    )


def _obtain_k8s_deployment(
    name: str, image: str, command: List[str], namespace: str = 'default',
    envs: List[client.V1EnvVar] = [], mounts: List[str] = [], pvc_specs: List[Dict] = [],
    replicas: int = 1, quota: Optional[Dict] = None, resources: Optional[Dict] = None,
    init_containers: List[client.V1Container] = [], labels: Optional[Dict[str, str]] = None,
    constraints: Optional[Dict] = None, secrets: str = ''
) -> client.V1Deployment:

    _resources = _convert_quota_to_k8s_resource(type='Resources', resources=resources) if resources \
        else _convert_quota_to_k8s_resource(resources=quota)

    node_selector = _convert_constraints_to_k8s_node_selector(constraints)

    _mounts, _volumes = _convert_mounts_to_k8s_volume(name, mounts, pvc_specs)

    return client.V1Deployment(
        api_version='apps/v1',
        kind='Deployment',
        metadata=client.V1ObjectMeta(
            name=name,
            labels=labels,
            namespace=namespace
        ),
        spec=client.V1DeploymentSpec(
            replicas=replicas,
            selector=client.V1LabelSelector(
                match_labels={MLAD_PROJECT_APP: name}
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
                    node_selector=node_selector,
                    image_pull_secrets=[client.V1LocalObjectReference(name=secrets)]
                    if secrets else None
                )
            )
        )
    )


def _obtain_k8s_pv(name: str, pv_index: int, pv_mount: Dict) -> client.V1PersistentVolume:
    return client.V1PersistentVolume(
        api_version='v1',
        kind='PersistentVolume',
        metadata=client.V1ObjectMeta(
            name=f'{name}-{pv_index}-pv',
            labels={
                'mount': f'{name}-{pv_index}',
                MLAD_PROJECT_APP: name
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


def _delete_k8s_pvs(name: str, cli: ApiClient = DEFAULT_CLI) -> None:
    api = client.CoreV1Api(cli)
    pvs = api.list_persistent_volume(label_selector=f'{MLAD_PROJECT_APP}={name}').items
    for pv in pvs:
        api.delete_persistent_volume(pv.metadata.name)


def _obtain_k8s_pvc(
    name: str, pv_index: int, namespace: str
) -> client.V1PersistentVolumeClaim:
    pvc_name = f'{name}-{pv_index}-pvc'
    return client.V1PersistentVolumeClaim(
        api_version='v1',
        kind='PersistentVolumeClaim',
        metadata=client.V1ObjectMeta(
            name=pvc_name,
            namespace=namespace
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


def _create_k8s_env(
    name: str, value: Optional[Union[str, int]] = None, field_path: str = None
) -> client.V1EnvVar:
    return client.V1EnvVar(
        name=name,
        value=str(value) if value is not None else None,
        value_from=client.V1EnvVarSource(
            field_ref=client.V1ObjectFieldSelector(
                field_path=field_path
            )
        ) if field_path else None
    )


def _obtain_k8s_service_for_app(expose: List[Dict], app_name: str, namespace: str,
                                labels: Dict[str, str]) -> client.V1Service:
    ports = set([item['port'] for item in expose])
    return client.V1Service(
        api_version='v1',
        kind='Service',
        metadata=client.V1ObjectMeta(
            name=app_name,
            namespace=namespace,
            labels=labels
        ),
        spec=client.V1ServiceSpec(
            selector={MLAD_PROJECT_APP: app_name},
            ports=[client.V1ServicePort(port=port, name=f'port{port}') for port in ports]
        )
    )


def obtain_k8s_app_resources(namespace: client.V1Namespace, base_labels: Dict[str, str],
                             name: str, app: Dict):
    resources = defaultdict(list)
    namespace_name = namespace.metadata.name
    namespace_labels = copy.deepcopy(namespace.metadata.labels)
    config_labels = copy.deepcopy(base_labels)
    project_key = config_labels[MLAD_PROJECT]
    project_name = config_labels[MLAD_PROJECT_NAME]
    image_name = config_labels[MLAD_PROJECT_IMAGE]
    project_base = config_labels[MLAD_PROJECT_BASE]
    user_name = config_labels[MLAD_PROJECT_USERNAME]
    kind = app['kind']
    image = app.get('image') or image_name
    quota = app.get('quota')
    app_envs = app.get('env') or {}
    app_envs.update({
        'PROJECT': project_name,
        'USERNAME': user_name,
        'PROJECT_KEY': project_key,
        'APP': name,
        'PYTHONUNBUFFERED': 1
    })
    config_envs = utils.decode_dict(config_labels[MLAD_PROJECT_ENV])
    config_envs = {env.split('=', 1)[0]: env.split('=', 1)[1] for env in config_envs}
    app_envs.update(config_envs)
    if quota is not None and quota['gpu'] == 0:
        app_envs.update({'NVIDIA_VISIBLE_DEVICES': 'none'})
    envs = [_create_k8s_env(k, v) for k, v in app_envs.items()]
    envs.append(_create_k8s_env('POD_NAME', field_path='metadata.name'))

    command = app.get('command') or []
    args = app.get('args') or []
    if isinstance(command, str):
        command = command.split()
    if isinstance(args, str):
        args = args.split()
    command += args

    labels = copy.copy(namespace_labels) or {}
    labels[MLAD_PROJECT_APP] = name

    constraints = app.get('constraints')
    pv_mounts = app.get('mounts') or []
    v_mounts = ['/etc/timezone:/etc/timezone:ro', '/etc/localtime:/etc/localtime:ro']

    config_labels[MLAD_PROJECT_APP] = name
    config_labels[MLAD_PROJECT_APP_KIND] = kind

    # Secrets
    secrets = f"{project_base}-auth"

    restart_policy = app['restartPolicy']
    init_containers = []
    if app.get('depends') is not None:
        init_containers = [_convert_depends_to_k8s_init_container(app['depends'], envs)]

    pvc_specs = []
    for pv_index, pv_mount in enumerate(pv_mounts):
        resources['pv'].append(_obtain_k8s_pv(name, pv_index, pv_mount))
        pvc = _obtain_k8s_pvc(name, pv_index, namespace_name)
        resources['pvc'].append(pvc)
        pvc_specs.append({
            'name': pvc.metadata.name,
            'mountPath': pv_mount['mountPath'],
            'readOnly': pv_mount['readOnly']
        })

    if kind == 'Job':
        resources['job'] = _obtain_k8s_job(
            name, image, command, namespace_name, restart_policy, envs, v_mounts, pvc_specs,
            1, None, quota, None, init_containers, labels, constraints, secrets)
    elif kind == 'Service':
        scale = app['scale']
        resources['deployment'] = _obtain_k8s_deployment(
            name, image, command, namespace_name, envs, v_mounts, pvc_specs, scale,
            quota, None, init_containers, labels, constraints, secrets)
    else:
        raise DeprecatedError

    ingress_specs = []
    if app.get('expose') is not None:
        resources['service'] = _obtain_k8s_service_for_app(app['expose'], name, namespace_name, labels)
        for expose in app['expose']:
            port = expose['port']
            ingress = expose.get('ingress')
            if ingress is not None:
                rewrite_path = ingress.get('rewritePath') or True
                ingress_path = ingress.get('path') or f'/{user_name}/{namespace_name}/{name}'
                ingress_specs.append({'port': port, 'path': ingress_path})
                k8s_ingress = _obtain_k8s_ingress(
                    namespace_name, name, port, ingress_path, rewrite_path
                )
                resources['ingress'].append(k8s_ingress)
    config_labels[MLAD_PROJECT_INGRESS] = json.dumps(ingress_specs)
    resources['configmap'] = obtain_k8s_config_map(f'app-{name}-labels', config_labels)
    return resources


def create_apps(namespace: client.V1Namespace, app_dict: Dict, cli: ApiClient = DEFAULT_CLI) -> List[App]:
    instances = []
    config_labels = _get_k8s_config_map_data(namespace, 'project-labels', cli)
    namespace_name = namespace.metadata.name
    for name, app in app_dict.items():
        resources = obtain_k8s_app_resources(namespace, config_labels, name, app)
        api = client.CoreV1Api(cli)
        api.create_namespaced_config_map(namespace_name, resources['configmap'])
        for pv in resources['pv']:
            api.create_persistent_volume(pv)
        for pvc in resources['pvc']:
            api.create_namespaced_persistent_volume_claim(namespace_name, pvc)
        if 'service' in resources:
            api.create_namespaced_service(namespace_name, resources['service'])
        api = client.NetworkingV1Api(cli)
        for ingress in resources['ingress']:
            api.create_namespaced_ingress(namespace_name, ingress)
        if 'job' in resources:
            api = client.BatchV1Api(cli)
            job = api.create_namespaced_job(namespace_name, resources['job'])
            instances.append(job)
        if 'deployment' in resources:
            api = client.AppsV1Api(cli)
            deployment = api.create_namespaced_deployment(namespace_name, resources['deployment'])
            instances.append(deployment)
    return instances


def update_apps(
    namespace: client.V1Namespace, update_yaml: Dict, update_specs: List[Dict], cli: ApiClient = DEFAULT_CLI
) -> List[App]:
    results = []
    for update_spec in update_specs:
        app_name = update_spec['name']
        if update_yaml['app'][app_name]['kind'] == 'Service':
            results.append(_update_k8s_deployment(namespace, update_spec, cli=cli))
        else:
            results.append(_update_k8s_job(namespace, update_spec, cli=cli))
    return results


def _update_k8s_deployment(
    namespace: client.V1Namespace, update_spec: Dict, cli: ApiClient = DEFAULT_CLI
) -> client.V1Deployment:
    app_name = update_spec['name']
    scale = update_spec['scale']
    command = update_spec['command'] or []
    args = update_spec['args'] or []
    quota = update_spec['quota'] or {}
    namespace_name = namespace.metadata.name

    resources = _convert_quota_to_k8s_resource(resources=quota).to_dict()

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
        namespace_spec = inspect_k8s_namespace(namespace, cli)
        body.append(_body("image", namespace_spec['image']))

    # update env
    deployment = get_k8s_deployment(app_name, namespace_name, cli)
    container_spec = deployment.spec.template.spec.containers[0]
    current = {env.name: env.value for env in container_spec.env}
    for key in list(update_spec['env']['current'].keys()):
        if key not in CONFIG_ENVS:
            current.pop(key)
    for key in list(update_spec['env']['update'].keys()):
        if key in CONFIG_ENVS:
            update_spec['env']['update'].pop(key)
    current.update(update_spec['env']['update'])
    if 'gpu' in quota and quota['gpu'] == 0:
        current.update({'NVIDIA_VISIBLE_DEVICES': 'none'})
    elif 'NVIDIA_VISIBLE_DEVICES' in current:
        del current['NVIDIA_VISIBLE_DEVICES']
    envs = [_create_k8s_env(k, v).to_dict() for k, v in current.items()]
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


def _update_k8s_job(
    namespace: client.V1Namespace, update_spec: Dict, cli: ApiClient = DEFAULT_CLI
) -> client.V1Job:
    app_name = update_spec['name']
    image = update_spec['image']
    command = update_spec['command'] or []
    args = update_spec['args'] or []
    quota = update_spec['quota'] or {}
    namespace_name = namespace.metadata.name

    resources = _convert_quota_to_k8s_resource(resources=quota)

    if isinstance(command, str):
        command = command.split()
    if isinstance(args, str):
        args = args.split()
    command += args

    k8s_job = get_app_from_kind(app_name, namespace_name, 'Job', cli=cli)
    # remove invalid properties to re-run the job
    k8s_job.metadata = client.V1ObjectMeta(name=k8s_job.metadata.name, labels=k8s_job.metadata.labels)
    k8s_job.spec.selector = None
    del k8s_job.spec.template.metadata.labels['controller-uid']

    container_spec = k8s_job.spec.template.spec.containers[0]
    current = {env.name: env.value for env in container_spec.env}
    for key in list(update_spec['env']['current'].keys()):
        if key not in CONFIG_ENVS:
            current.pop(key)
    for key in list(update_spec['env']['update'].keys()):
        if key in CONFIG_ENVS:
            update_spec['env']['update'].pop(key)
    current.update(update_spec['env']['update'])
    if 'gpu' in quota and quota['gpu'] == 0:
        current.update({'NVIDIA_VISIBLE_DEVICES': 'none'})
    elif 'NVIDIA_VISIBLE_DEVICES' in current:
        del current['NVIDIA_VISIBLE_DEVICES']
    env = [client.V1EnvVar(name=k, value=v).to_dict() for k, v in current.items()]

    container_spec.command = command
    container_spec.resources = resources
    if image is not None:
        container_spec.image = image
    else:
        namespace_spec = inspect_k8s_namespace(namespace, cli)
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


def _delete_k8s_job(name: str, namespace: str, cli: ApiClient = DEFAULT_CLI) -> client.V1Job:
    api = client.BatchV1Api(cli)
    return api.delete_namespaced_job(name, namespace, propagation_policy='Foreground')


def _delete_k8s_deployment(
    name: str, namespace: str, cli: ApiClient = DEFAULT_CLI
) -> client.V1Deployment:
    api = client.AppsV1Api(cli)
    return api.delete_namespaced_deployment(name, namespace, propagation_policy='Foreground')


def remove_apps(
    apps: List[App], namespace: str, disconnect_handler: Optional[object] = None,
    cli: ApiClient = DEFAULT_CLI
) -> LogGenerator:
    api = client.CoreV1Api(cli)
    network_api = client.NetworkingV1Api(cli)

    def _get_app_spec(app):
        spec = inspect_app(app, cli)
        app_name = spec['name']
        task_keys = list(spec['task_dict'].keys())

        config_labels = _get_k8s_config_map_data(namespace, f'app-{app_name}-labels', cli)
        kind = config_labels[MLAD_PROJECT_APP_KIND]
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
            _delete_k8s_pvs(app_name)
            if kind == 'Job':
                _delete_k8s_job(app_name, namespace, cli=cli)
            elif kind == 'Service':
                _delete_k8s_deployment(app_name, namespace, cli=cli)

            if get_k8s_service_of_app(namespace, app_name, cli=cli) is not None:
                api.delete_namespaced_service(app_name, namespace)

            ingress_list = network_api.list_namespaced_ingress(
                namespace, label_selector=f'{MLAD_PROJECT_APP}={app_name}').items
            if len(ingress_list) > 0:
                ingress_name = ingress_list[0].metadata.name
                network_api.delete_namespaced_ingress(ingress_name, namespace)
        except ApiException as e:
            print("Exception when calling ExtensionsV1beta1Api->delete_namespaced_ingress: %s\n" % e)

    for stream in collector:
        yield stream


def get_k8s_nodes(cli: ApiClient = DEFAULT_CLI) -> List[client.V1Node]:
    api = client.CoreV1Api(cli)
    return api.list_node().items


def inspect_k8s_node(node: client.V1Node) -> Dict:
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


@handle_k8s_exception('node')
def enable_k8s_node(name: str, cli: ApiClient = DEFAULT_CLI) -> client.V1Node:
    api = client.CoreV1Api(cli)
    body = {
        "spec": {"taints": None}
    }
    return api.patch_node(name, body)


@handle_k8s_exception('node')
def disable_k8s_node(name: str, cli: ApiClient = DEFAULT_CLI) -> client.V1Node:
    api = client.CoreV1Api(cli)
    body = {
        "spec": {"taints": [{"effect": "NoSchedule",
                            "key": "node-role.kubernetes.io/worker"}]}
    }
    return api.patch_node(name, body)


@handle_k8s_exception('node')
def delete_k8s_node(name: str, cli: ApiClient = DEFAULT_CLI) -> client.V1Node:
    api = client.CoreV1Api(cli)
    return api.delete_node(name)


@handle_k8s_exception('node')
def add_k8s_node_labels(name: str, cli: ApiClient = DEFAULT_CLI, **kv: str) -> client.V1Node:
    api = client.CoreV1Api(cli)
    body = {
        "metadata": {
            "labels": dict()
        }
    }
    for key in kv:
        body['metadata']['labels'][key] = kv[key]
    return api.patch_node(name, body)


@handle_k8s_exception('node')
def remove_k8s_node_labels(
    name: str, cli: ApiClient = DEFAULT_CLI, *keys: str
) -> client.V1Node:
    api = client.CoreV1Api(cli)
    body = {
        "metadata": {
            "labels": dict()
        }
    }
    for key in keys:
        body['metadata']['labels'][key] = None
    return api.patch_node(name, body)


def scale_app(app: App, scale_spec: int, cli: ApiClient = DEFAULT_CLI) -> client.V1Scale:
    name = app.metadata.name
    namespace = app.metadata.namespace
    api = client.AppsV1Api(cli)
    body = {
        "spec": {
            "replicas": scale_spec
        }
    }
    try:
        return api.patch_namespaced_deployment_scale(name=name, namespace=namespace, body=body)
    except ApiException as e:
        msg, status = exceptions.handle_k8s_api_error(e)
        if status == 404:
            raise exceptions.NotFound(f'Cannot find app {name} in {namespace}.')
        else:
            raise exceptions.APIError(msg, status)


def _filter_app_and_pod_name_tuple_from_apps(
    project_key: str, filters: Optional[List[str]], cli: ApiClient = DEFAULT_CLI
) -> List[Tuple[Optional[str], str]]:
    api = client.CoreV1Api(cli)
    apps = get_apps(project_key, cli=cli)
    namespace = get_k8s_namespace(project_key, cli=cli).metadata.name

    selected_tuples = []
    app_and_pod_names = [(spec['name'], list(spec['task_dict'].keys())) for spec in inspect_apps(apps, cli)]
    for app_name, pod_names in app_and_pod_names:
        if filters is None:
            selected_tuples += [(app_name, pod_name) for pod_name in pod_names]
            continue
        elif app_name in filters:
            selected_tuples += [(app_name, pod_name) for pod_name in pod_names]
            continue
        for pod_name in pod_names:
            if pod_name in filters:
                selected_tuples.append((None, pod_name))

    # check whether targets are pending or not
    filtered_tuples = []
    for app_name, pod_name in selected_tuples:
        pod = api.read_namespaced_pod(name=pod_name, namespace=namespace)
        phase = get_pod_info(pod, cli)['phase']
        if not phase == 'Pending':
            filtered_tuples.append((app_name, pod_name))

    if len(filtered_tuples) == 0:
        raise exceptions.NotFound('Cannot find a running app or tasks in project')

    return filtered_tuples


def get_project_logs(
    project_key: str, filters: Optional[List[str]] = None, tail: str = 'all', follow: bool = False,
    timestamps: bool = False, disconnect_handler: Optional[object] = None, cli: ApiClient = DEFAULT_CLI
) -> Generator[Dict, None, None]:
    app_and_pod_name_tuples = _filter_app_and_pod_name_tuple_from_apps(project_key, filters, cli=cli)
    namespace = get_k8s_namespace(project_key, cli=cli).metadata.name

    handler = LogHandler(cli, namespace, tail)
    monitoring_app_names = set([app_name for app_name, _ in app_and_pod_name_tuples if app_name is not None])

    with LogCollector(follow, timestamps) as collector:
        collector.collect_logs([pod_name for _, pod_name in app_and_pod_name_tuples], handler)
        # Register Disconnection Callback
        if disconnect_handler is not None:
            disconnect_handler.add_callback(lambda: handler.close())
        if follow and len(monitoring_app_names) > 0:
            monitor = LogMonitor(cli, handler, collector, namespace, monitoring_app_names,
                                 last_resource=None, follow=follow, tail=tail, timestamps=timestamps)
            monitor.start()
            if disconnect_handler is not None:
                disconnect_handler.add_callback(lambda: monitor.stop())
        yield from collector


def _obtain_k8s_ingress(
    namespace: str, app_name: str, port: int, base_path: str = '/',
    rewrite: bool = False
) -> client.V1Ingress:
    ingress_name = f'{app_name}-ingress-{port}'
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
    return client.V1Ingress(
        api_version="networking.k8s.io/v1",
        kind="Ingress",
        metadata=client.V1ObjectMeta(name=ingress_name, annotations=annotations,
                                     namespace=namespace,
                                     labels={MLAD_PROJECT_APP: app_name}),
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


def parse_mem(str_mem: str) -> float:
    if str_mem.endswith('Ki'):
        mem = float(str_mem[:-2]) / 1024
    elif str_mem.endswith('K') or str_mem.endswith('k'):
        mem = float(str_mem[:-1]) / 1000
    elif str_mem.endswith('Mi'):
        mem = float(str_mem[:-2])
    elif str_mem.endswith('M'):
        mem = float(str_mem[:-1])
    elif str_mem.endswith('Gi'):
        mem = float(str_mem[:-2]) * 1024
    elif str_mem.endswith('G'):
        mem = float(str_mem[:-1]) * 1000
    else:
        # TODO Other units may need to be considered
        try:
            mem = float(str_mem)
        except ValueError:
            raise InvalidMetricUnitError('mem', str_mem)
    return float(round(mem, 1))


def parse_cpu(str_cpu: str) -> float:
    if str_cpu.endswith('n'):
        cpu = float(str_cpu[:-1]) / 1e9
    elif str_cpu.endswith('u'):
        cpu = float(str_cpu[:-1]) / 1e6
    elif str_cpu.endswith('m'):
        cpu = float(str_cpu[:-1]) / 1e3
    else:
        # TODO Other units may need to be considered
        try:
            cpu = float(str_cpu)
        except ValueError:
            raise InvalidMetricUnitError('cpu', str_cpu)
    return cpu


def parse_gpu(str_gpu: Optional[str]) -> int:
    if str_gpu is None:
        return 0
    try:
        return int(str_gpu)
    except ValueError:
        raise InvalidMetricUnitError('gpu', str_gpu)


def get_k8s_node_resources(
    node: client.V1Node, no_trunc: bool, cli: ApiClient = DEFAULT_CLI
) -> Dict:
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

    gpu_request = 0
    cpu_request = 0
    mem_request = 0
    selector = (f'spec.nodeName={name},status.phase!=Succeeded,status.phase!=Failed')
    pods = v1_api.list_pod_for_all_namespaces(field_selector=selector)
    for pod in pods.items:
        for container in pod.spec.containers:
            requests = defaultdict(lambda: '0', container.resources.requests or {})
            gpu_request += parse_gpu(requests['nvidia.com/gpu'])
            cpu_request += parse_cpu(requests['cpu'])
            mem_request += parse_mem(requests['memory'])
    used_gpu = gpu_request

    result = {
        'mem': {'capacity': mem, 'used': used_mem, 'request': mem_request,
                'allocatable': mem - used_mem if not isinstance(used_mem, str) else '-'},
        'cpu': {'capacity': cpu, 'used': used_cpu, 'request': cpu_request,
                'allocatable': cpu - used_cpu if not isinstance(used_cpu, str) else '-'},
        'gpu': {'capacity': gpu, 'used': used_gpu, 'request': gpu_request,
                'allocatable': gpu - used_gpu},
    }

    if not no_trunc:
        for resource, value in result.items():
            for k in value:
                if not isinstance(result[resource][k], str):
                    result[resource][k] = round(result[resource][k], 1)

    return result


def get_project_resources(
    project_key: str, group_by: str = 'project', no_trunc: bool = True,
    cli: ApiClient = DEFAULT_CLI
) -> Dict:
    api = client.CustomObjectsApi(cli)
    v1_api = client.CoreV1Api(cli)
    result = {}
    project_result = {'cpu': 0, 'gpu': 0, 'mem': 0}
    apps = get_apps(project_key, cli=cli)

    def aggregate_gpu_value(pod):
        used = 0
        for container in pod.spec.containers:
            requests = defaultdict(lambda: '0', container.resources.requests or {})
            gpu = parse_gpu(requests['nvidia.com/gpu'])
            used += gpu
        return used

    cpu_unit_error = False
    mem_unit_error = False
    for app in apps:
        name = app.metadata.labels[MLAD_PROJECT_APP]
        namespace = app.metadata.namespace
        result[name] = {}

        pods = v1_api.list_namespaced_pod(namespace,
                                          label_selector=f'{MLAD_PROJECT_APP}={name}')
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

                pod_gpu_usage = aggregate_gpu_value(pod)
                if pod_gpu_usage is not None:
                    resource['gpu'] += pod_gpu_usage

                if group_by == 'project':
                    for k in project_result:
                        project_result[k] += resource[k] if not isinstance(resource[k], str) else 0

                if not no_trunc:
                    for k in resource:
                        resource[k] = round(resource[k], 1) if not isinstance(resource[k], str) \
                            else resource[k]

                result[name][pod_name] = resource

            except ApiException as e:
                if e.headers['Content-Type'] == 'application/json':
                    body = json.loads(e.body)
                    if body['kind'] == 'Status':
                        print(f"{body['status']} : {body['message']}")
                    result[name][pod_name] = {'mem': 'NotReady', 'cpu': 'NotReady', 'gpu': 'NotReady'}
                elif e.status == 404 or e.status == 503:
                    print('Metrics server unavailable.')
                    result[name][pod_name] = {'mem': '-', 'cpu': '-', 'gpu': '-'}
                continue

    if group_by == 'project':
        if cpu_unit_error:
            project_result['cpu'] = 'UnitError'
        if mem_unit_error:
            project_result['mem'] = 'UnitError'

        if not no_trunc:
            for k in project_result:
                project_result[k] = round(project_result[k], 1) if not isinstance(project_result[k], str) \
                    else project_result[k]

        return project_result
    elif group_by == 'app':
        return result


def set_default_session_quota(cpu: float, gpu: int, mem: str, cli: ApiClient = DEFAULT_CLI):
    api = client.CoreV1Api(cli)
    name = 'mlad-api-server-quota-config'
    configmap: client.V1ConfigMap = api.read_namespaced_config_map(name, 'mlad')
    configmap.data.update({
        'default.cpu': str(cpu),
        'default.gpu': str(gpu),
        'default.mem': mem
    })

    api.patch_namespaced_config_map(name, 'mlad', configmap)


def set_session_quota(session: str, cpu: float, gpu: int, mem: str, cli: ApiClient = DEFAULT_CLI):

    payload = jwt.decode(session, 'mlad', algorithms=['HS256'])
    username = payload['user']
    hostname = payload['hostname']

    api = client.CoreV1Api(cli)
    name = 'mlad-api-server-quota-config'
    configmap: client.V1ConfigMap = api.read_namespaced_config_map(name, 'mlad')
    configmap.data.update({
        f'{username}.{hostname}.cpu': str(cpu),
        f'{username}.{hostname}.gpu': str(gpu),
        f'{username}.{hostname}.mem': mem
    })

    api.patch_namespaced_config_map(name, 'mlad', configmap)


def check_session_quota(
    session: str, quotas: List[Union[None, Dict]], cli: ApiClient = DEFAULT_CLI
):
    req_cpu = 0
    req_gpu = 0
    req_mem = 0
    for quota in quotas:
        if quota is None:
            continue
        req_cpu += quota['cpu'] or 0
        req_gpu += quota['gpu'] or 0
        req_mem += parse_mem(quota['mem'] or '0')
    payload = jwt.decode(session, 'mlad', algorithms=['HS256'])
    username = payload['user']
    hostname = payload['hostname']
    name = 'mlad-api-server-quota-config'
    core_api = client.CoreV1Api(cli)
    batch_api = client.BatchV1Api(cli)
    quota_dict = core_api.read_namespaced_config_map(name, 'mlad').data
    pod_list: client.V1PodList = core_api.list_pod_for_all_namespaces(
        label_selector=f'{MLAD_PROJECT_HOSTNAME}={hostname},{MLAD_PROJECT_USERNAME}={username}',
    )
    cpu_key = f'{username}.{hostname}.cpu'
    gpu_key = f'{username}.{hostname}.gpu'
    mem_key = f'{username}.{hostname}.mem'
    total_cpu = float(quota_dict[cpu_key] if cpu_key in quota_dict else quota_dict['default.cpu'])
    total_gpu = int(quota_dict[gpu_key] if gpu_key in quota_dict else quota_dict['default.gpu'])
    total_mem = parse_mem(quota_dict[mem_key] if mem_key in quota_dict else quota_dict['default.mem'])
    for pod in pod_list.items:
        if pod.metadata.owner_references[0].kind == 'Job':
            app_name = pod.metadata.labels[MLAD_PROJECT_APP]
            namespace = pod.metadata.namespace
            job_status = batch_api.read_namespaced_job(app_name, namespace).status
            if job_status.active is None:
                continue
        for container in pod.spec.containers:
            requests = defaultdict(lambda: '0', container.resources.requests or {})
            total_cpu -= parse_cpu(requests['cpu'])
            total_gpu -= parse_gpu(requests['nvidia.com/gpu'])
            total_mem -= parse_mem(requests['memory'])

    if total_cpu < req_cpu or total_gpu < req_gpu or total_mem < req_mem:
        raise InsufficientSessionQuotaError(username, hostname)


def obtain_resources_by_session(cli=DEFAULT_CLI):
    api = client.CoreV1Api(cli)
    resp: client.V1PodList = api.list_pod_for_all_namespaces(
        label_selector=f'{MLAD_PROJECT_API_VERSION}=v1',
        field_selector='status.phase=Running'
    )

    # Dict structure: {node_name: {user@hostname: {cpu: 0, gpu: 0, mem: 0}}}
    ret = defaultdict(lambda: defaultdict(lambda: {'cpu': 0, 'gpu': 0, 'mem': 0}))

    pod: client.V1Pod
    for pod in resp.items:
        labels = pod.metadata.labels
        username = labels[MLAD_PROJECT_USERNAME]
        hostname = labels[MLAD_PROJECT_HOSTNAME]
        name = f'{username}@{hostname}'
        node_name = pod.spec.node_name
        container: client.V1Container
        for container in pod.spec.containers:
            requests = defaultdict(lambda: '0', container.resources.requests or {})
            try:
                cpu = parse_cpu(requests['cpu'])
                gpu = parse_gpu(requests['nvidia.com/gpu'])
                mem = parse_mem(requests['memory'])
            except InvalidMetricUnitError as e:
                print('InvalidMetricUnitError', e.metric, e.value)
                if e.metric == 'cpu':
                    cpu = 0
                elif e.metric == 'gpu':
                    gpu = 0
                elif e.metric == 'mem':
                    mem = 0
            ret[node_name][name]['cpu'] += cpu
            ret[node_name][name]['gpu'] += gpu
            ret[node_name][name]['mem'] += mem
    return ret
