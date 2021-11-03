import json
import base64

from typing import List

import docker

from mlad.cli.exceptions import (
    DockerNotFoundError
)


def get_cli() -> docker.client.DockerClient:
    try:
        return docker.from_env()
    except Exception:
        raise DockerNotFoundError


def obtain_credential():
    cli = get_cli()
    headers = {'X-Registry-Config': b''}
    docker.api.build.BuildApiMixin._set_auth_headers(cli.api, headers)
    headers = {'auths': json.loads(
        base64.urlsafe_b64decode(headers['X-Registry-Config'] or b'e30K')
    )}
    encoded = base64.urlsafe_b64encode(json.dumps(headers).encode())
    return encoded.decode()


def get_images(project_key: str = None, extra_labels: List[str] = []):
    cli = get_cli()
    filters = ['MLAD.PROJECT.API_VERSION=v1']
    if project_key:
        filters += [f'MLAD.PROJECT={project_key}']
    return cli.images.list(filters={'label': filters + extra_labels})


def push_image(tag: str):
    cli = get_cli()
    try:
        lines = cli.images.push(tag, stream=True, decode=True)
        for line in lines:
            if 'error' in line:
                raise docker.errors.APIError(line['error'], None)
            yield line['stream']
    except StopIteration:
        pass
