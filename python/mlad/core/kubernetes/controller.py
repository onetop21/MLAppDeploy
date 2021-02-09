import sys
import copy
import time
import json
import uuid
import base64
from pathlib import Path
from typing import Dict, List
import requests
from mlad.core import exception
from mlad.core.libs import utils
#from mlad.core.docker.logs import LogHandler, LogCollector
from mlad.core.default import project_service as service_default
from kubernetes import client, config, watch
from kubernetes.client.rest import ApiException

# https://github.com/kubernetes-client/python/blob/release-11.0/kubernetes/docs/CoreV1Api.md

SHORT_LEN = 10
config.load_kube_config()

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


if __name__ == '__main__':
    v1 = client.CoreV1Api()
    #ret = get_project_networks(cli)
    body = client.V1Namespace(metadata=client.V1ObjectMeta(name="hello-cluster", labels={'MLAD.PROJECT': '123', 'MLAD.PROJECT.NAME':'hello'}))
    try:
        ret = v1.create_namespace(body)
        print(ret)
    except ApiException as e:
        print(f"Exception Handling v1.create_namespace => {e}", file=sys.stderr)
    ret = v1.list_namespace(label_selector="MLAD.PROJECT=123", watch=False)
    print('Project Networks', [_.metadata.name for _ in ret.items])
    namespace = [_.metadata.name for _ in ret.items][-1]

    body = client.V1ReplicationController()
    body.metadata = client.V1ObjectMeta()
    body.metadata.name = 'test'
    body.metadata.labels = {'MLAD.PROJECT': '123', 'MLAD.PROJECt.SERVICE': 'test' }
    body.spec = client.V1ReplicationControllerSpec()
    body.spec.replicas = 3
    body.spec.selector = {'app': body.metadata.name}
    body.spec.template = client.V1PodTemplateSpec()
    body.spec.template.metadata = client.V1ObjectMeta()
    body.spec.template.metadata.name = body.metadata.name
    body.spec.template.metadata.labels = {'app': body.metadata.name}
    container = client.V1Container(name=body.metadata.name)
    container.image = 'ubuntu:latest'
    container.args=['sleep', '30']
    container.restart_policy='Never'
    body.spec.template.spec = client.V1PodSpec(containers=[container])
    try:
        ret = v1.create_namespaced_replication_controller(namespace, body)
    except ApiException as e:
        print(f"Exception Handling v1.create_namespaced_replication_controller => {e}", file=sys.stderr)
        ret = v1.delete_namespaced_replication_controller(body.metadata.name, namespace, propagation_policy='Foreground')
    print(ret)


