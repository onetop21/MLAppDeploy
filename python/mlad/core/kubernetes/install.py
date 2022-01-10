import json
import base64

from datetime import datetime
from pathlib import Path

from kubernetes import client
from kubernetes.client.rest import ApiException


def _handle_already_exists_exception(e):
    body = json.loads(e.body)
    if 'reason' in body and body['reason'] == 'AlreadyExists':
        pass
    else:
        raise e


def _handle_not_found_exception(e):
    body = json.loads(e.body)
    if 'reason' in body and body['reason'] == 'NotFound':
        pass
    else:
        raise e


def create_docker_registry_secret(cli):
    api = client.CoreV1Api(cli)
    with open(f'{Path.home()}/.docker/config.json', 'rb') as config_file:
        data = {
            '.dockerconfigjson': base64.b64encode(config_file.read()).decode()
        }
    secret = client.V1Secret(
        api_version='v1',
        data=data,
        kind='Secret',
        metadata=dict(name='docker-mlad-sc', namespace='mlad'),
        type='kubernetes.io/dockerconfigjson'
    )
    try:
        api.create_namespaced_secret('mlad', secret)
    except ApiException as e:
        _handle_already_exists_exception(e)


def create_mlad_namespace(cli):
    api = client.CoreV1Api(cli)
    try:
        api.create_namespace(
            client.V1Namespace(metadata=client.V1ObjectMeta(name='mlad'))
        )
    except ApiException as e:
        _handle_already_exists_exception(e)


def create_api_server_role_and_rolebinding(cli):
    api = client.RbacAuthorizationV1Api(cli)
    cluster_role = client.V1ClusterRole(
        api_version='rbac.authorization.k8s.io/v1',
        kind='ClusterRole',
        metadata=client.V1ObjectMeta(name='mlad-cluster-role'),
        rules=[
            client.V1PolicyRule(
                api_groups=[
                    '', 'apps', 'batch', 'extensions', 'rbac.authorization.k8s.io',
                    'networking.k8s.io', 'metrics.k8s.io'
                ],
                resources=[
                    'nodes', 'namespaces', 'services', 'pods', 'pods/log', 'replicationcontrollers',
                    'deployments', 'deployments/scale', 'replicaset', 'jobs', 'configmaps',
                    'secrets', 'events', 'rolebindings', 'ingresses', 'podmetrics'
                ],
                verbs=[
                    'get', 'watch', 'list', 'create', 'update', 'delete', 'patch',
                    'deletecollection'
                ]
            )
        ]
    )

    cluster_role_binding = client.V1ClusterRoleBinding(
        api_version='rbac.authorization.k8s.io/v1',
        kind='ClusterRoleBinding',
        metadata=client.V1ObjectMeta(name='mlad-cluster-role-binding'),
        role_ref=client.V1RoleRef(
            api_group='rbac.authorization.k8s.io',
            kind='ClusterRole',
            name='mlad-cluster-role'
        ),
        subjects=[
            client.V1Subject(
                kind='ServiceAccount',
                name='default',
                namespace='mlad'
            )
        ]
    )

    try:
        api.create_cluster_role(body=cluster_role)
    except ApiException as e:
        _handle_already_exists_exception(e)

    try:
        api.create_cluster_role_binding(body=cluster_role_binding)
    except ApiException as e:
        _handle_already_exists_exception(e)


def create_mlad_service(cli, nodeport: bool = True, beta: bool = False):
    api = client.CoreV1Api(cli)
    service_name = 'mlad-service' if not beta else 'mlad-service-beta'
    pod_name = 'mlad-api-server' if not beta else 'mlad-api-server-beta'
    service = client.V1Service(
        api_version='v1',
        kind='Service',
        metadata=client.V1ObjectMeta(
            name=service_name,
            namespace='mlad',
            labels={'app': pod_name}
        ),
        spec=client.V1ServiceSpec(
            selector={'app': pod_name},
            type='ClusterIP' if not nodeport else 'NodePort',
            ports=[client.V1ServicePort(port=8440, target_port=8440, name='mlad-port')]
        )
    )
    try:
        api.create_namespaced_service('mlad', body=service)
    except ApiException as e:
        _handle_already_exists_exception(e)


def create_mlad_api_server_deployment(cli, image_tag: str, beta: bool = False):
    api = client.AppsV1Api(cli)
    name = 'mlad-api-server' if not beta else 'mlad-api-server-beta'
    deployment = client.V1Deployment(
        metadata=client.V1ObjectMeta(
            name=name,
            namespace='mlad'
        ),
        spec=client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(
                match_labels={'app': name}
            ),
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(
                    name=f'{name}-pod',
                    labels={'app': name}
                ),
                spec=client.V1PodSpec(
                    restart_policy='Always',
                    termination_grace_period_seconds=10,
                    containers=[client.V1Container(
                        name=name,
                        image=image_tag,
                        image_pull_policy='Always',
                        env=[
                            client.V1EnvVar(name='MLAD_DEBUG', value='1'),
                            client.V1EnvVar(name='MLAD_KUBE', value='1'),
                            client.V1EnvVar(name='PYTHONUNBUFFERED', value='1'),
                        ],
                        ports=[
                            client.V1ContainerPort(name='http', container_port=8440)
                        ]
                    )],
                    image_pull_secrets=[client.V1LocalObjectReference(name='docker-mlad-sc')]
                )
            )
        )
    )

    try:
        api.create_namespaced_deployment('mlad', body=deployment)
    except ApiException as e:
        _handle_already_exists_exception(e)


def create_mlad_ingress(cli, beta: bool = False):
    api = client.NetworkingV1Api(cli)
    annotations = {
        "kubernetes.io/ingress.class": "nginx",
        "nginx.ingress.kubernetes.io/proxy-body-size": "0",
        "nginx.ingress.kubernetes.io/proxy-read-timeout": "600",
        "nginx.ingress.kubernetes.io/proxy-send-timeout": "600",
    }
    if beta:
        annotations['nginx.ingress.kubernetes.io/rewrite-target'] = '/$2'

    ingress_name = 'mlad-ingress' if not beta else 'mlad-ingress-beta'
    service_name = 'mlad-service' if not beta else 'mlad-service-beta'
    path = '/' if not beta else '/beta(/|$)(.*)'
    ingress = client.V1Ingress(
        api_version="networking.k8s.io/v1",
        kind="Ingress",
        metadata=client.V1ObjectMeta(
            name=ingress_name, namespace='mlad', annotations=annotations),
        spec=client.V1IngressSpec(
            rules=[
                client.V1IngressRule(
                    http=client.V1HTTPIngressRuleValue(
                        paths=[client.V1HTTPIngressPath(
                            path=path,
                            path_type='ImplementationSpecific',
                            backend=client.V1IngressBackend(
                                service=client.V1IngressServiceBackend(
                                    name=service_name,
                                    port=client.V1ServiceBackendPort(
                                        number=8440
                                    )
                                )
                            )
                        )]
                    )
                )
            ]
        )
    )

    try:
        api.create_namespaced_ingress('mlad', body=ingress)
    except ApiException as e:
        _handle_already_exists_exception(e)


def delete_mlad_ingress(cli, beta: bool = False):
    api = client.NetworkingV1Api(cli)
    try:
        name = 'mlad-ingress' if not beta else 'mlad-ingress-beta'
        api.delete_namespaced_ingress(name, 'mlad')
    except ApiException as e:
        _handle_not_found_exception(e)


def patch_mlad_service(cli, nodeport: bool = True, beta: bool = False):
    api = client.CoreV1Api(cli)
    pod_name = 'mlad-api-server' if not beta else 'mlad-api-server-beta'
    service_name = 'mlad-service' if not beta else 'mlad-service-beta'
    port_type = 'ClusterIP' if not nodeport else 'NodePort'
    body = [
        {'op': 'replace', 'path': '/spec/type', 'value': port_type},
        {'op': 'replace', 'path': '/spec/ports/0/nodePort', 'value': None}
    ]
    res = api.list_namespaced_service('mlad', label_selector=f'app={pod_name}')
    service_exists = len(res.items) == 1

    if service_exists:
        api.patch_namespaced_service(service_name, 'mlad', body=body)


def patch_mlad_api_server_deployment(cli, beta: bool = False):
    api = client.AppsV1Api(cli)
    now = datetime.utcnow()
    now = str(now.isoformat('T') + 'Z')
    body = {
        'spec': {
            'template': {
                'metadata': {
                    'annotations': {
                        'kubectl.kubernetes.io/restartedAt': now
                    }
                }
            }
        }
    }
    name = 'mlad-api-server' if not beta else 'mlad-api-server-beta'
    api.patch_namespaced_deployment(name, 'mlad', body=body)
