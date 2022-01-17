import os
import pwd
import json
import base64
import requests_unixsocket

from typing import List, Optional

import docker
from docker.types import Mount
from mlad.core.libs import utils
from mlad.core.exceptions import (
    DockerNotFoundError
)


def get_cli() -> docker.client.DockerClient:
    try:
        return docker.from_env()
    except Exception:
        raise DockerNotFoundError


def _get_auth_headers():
    cli = get_cli()
    headers = {'X-Registry-Config': b''}
    docker.api.build.BuildApiMixin._set_auth_headers(cli.api, headers)
    return headers


def obtain_credential():
    headers = _get_auth_headers()
    headers = {'auths': json.loads(
        base64.urlsafe_b64decode(headers['X-Registry-Config'] or b'e30K')
    )}
    encoded = base64.urlsafe_b64encode(json.dumps(headers).encode())
    return encoded.decode()


def get_image(image_name: str):
    cli = get_cli()
    return cli.images.get(image_name)


def get_images(project_key: str = None, extra_labels: List[str] = []):
    cli = get_cli()
    filters = ['MLAD.PROJECT.API_VERSION=v1']
    if project_key:
        filters += [f'MLAD.PROJECT={project_key}']
    return cli.images.list(filters={'label': filters + extra_labels})


def inspect_image(image: docker.models.images.Image):
    return {
        # For image
        'id': image.id.split(':', 1)[-1],
        'short_id': image.short_id.split(':', 1)[-1],
        'tag': image.labels['MLAD.PROJECT.IMAGE'],
        'tags': image.tags,
        'version': image.labels['MLAD.PROJECT.VERSION'],
        'username': image.labels['MLAD.PROJECT.USERNAME'],
        'maintainer': image.attrs['Author'],
        # Trim meaningless decimals
        'created': image.attrs['Created'][:-7],
        # For project
        'api_version': image.labels['MLAD.PROJECT.API_VERSION'],
        'workspace': image.labels['MLAD.PROJECT.WORKSPACE'] if 'MLAD.PROJECT.WORKSPACE' in image.labels else 'Not Supported',
        'project_name': image.labels['MLAD.PROJECT.NAME'],
    }


def build_image(base_labels, tar, dockerfile, no_cache=False, pull=False, stream=False):
    cli = get_cli()
    latest_name = base_labels['MLAD.PROJECT.IMAGE']
    headers = _get_auth_headers()
    headers['content-type'] = 'application/x-tar'

    params = {
        'dockerfile': dockerfile,
        't': latest_name,
        'labels': json.dumps(base_labels),
        'forcerm': 1,
        'nocache': no_cache,
        'pull': pull
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
            if 'error' in _:
                return (None, resp_stream)
        return (get_image(cli, latest_name), resp_stream)


def push_image(tag: str):
    cli = get_cli()
    try:
        lines = cli.images.push(tag, stream=True, decode=True)
        for line in lines:
            if 'error' in line:
                raise docker.errors.APIError(line['error'], None)
            elif 'stream' in line:
                yield line['stream']
    except StopIteration:
        pass


def remove_image(ids: List[str], force=False):
    cli = get_cli()
    return [cli.images.remove(_id, force=force) for _id in ids]


def prune_images(project_key: Optional[str] = None):
    cli = get_cli()
    filters = ['MLAD.PROJECT.API_VERSION=v1']
    if project_key is not None:
        filters += [f'MLAD.PROJECT={project_key}']
    return cli.images.prune(filters={'label': filters, 'dangling': True})


def run_nfs_container(project_key: str, path: str, port: str):
    cli = get_cli()
    pwuid = pwd.getpwuid(os.getuid())
    uid = pwuid.pw_uid
    gid = pwuid.pw_gid
    cli.containers.run(
        'ghcr.io/onetop21/nfs-server-alpine',
        privileged=True,
        environment=[
            'SHARED_DIRECTORY=/shared',
            'SQUASH=1',
            f'ANONUID={uid}',
            f'ANONGID={gid}'
        ],
        ports={'2049/tcp': port},
        mounts=[Mount(source=path, target='/shared', type='bind')],
        detach=True,
        labels={
            'MLAD.PROJECT': project_key,
            'role': 'nfs-server'
        },
        restart_policy={'Name': 'always'}
    )


def remove_nfs_containers(project_key: str):
    cli = get_cli()
    containers = cli.containers.list(
        filters={'label': [f'MLAD.PROJECT={project_key}', 'role=nfs-server']},
        all=True)
    for container in containers:
        container.stop()
        container.remove()
