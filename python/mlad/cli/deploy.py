import sys

from typing import Optional, List, Tuple

from mlad.cli import config as config_core
from mlad.cli import train
from mlad.cli.libs import utils, interrupt_handler
from mlad.cli.validator import validators
from mlad.cli.exceptions import (
    ImageNotFoundError, InvalidProjectKindError
)

from mlad.core.docker import controller2 as docker_ctlr
from mlad.core.default import project as default_project
from mlad.core.libs import utils as core_utils

from mlad.api import API


def serve(file: Optional[str]):

    utils.process_file(file)
    config = config_core.get()
    project = utils.get_project(default_project)
    project = validators.validate(project)

    kind = project['kind']
    if not kind == 'Deployment':
        raise InvalidProjectKindError('Deployment', 'deploy')

    base_labels = core_utils.base_labels(
        utils.get_workspace(),
        config.session,
        project)

    project_key = base_labels['MLAD.PROJECT']

    # Find suitable image
    base_key = base_labels['MLAD.PROJECT'].rsplit('-', 1)[0]
    image_tag = base_labels['MLAD.PROJECT.IMAGE']
    images = [image for image in docker_ctlr.get_images(project_key=base_key)
              if image_tag in image.tags]
    if len(images) == 0:
        raise ImageNotFoundError(image_tag)
    image = images[0]

    # Re-tag the image
    registry_address = utils.get_registry_address(config)
    image_tag = f'{registry_address}/{image_tag}'
    image.tag(image_tag)
    base_labels['MLAD.PROJECT.IMAGE'] = image_tag

    # Push image
    yield f'Upload the image to the registry [{registry_address}]...'
    for line in docker_ctlr.push_image(image_tag):
        yield line

    # Create a project
    yield 'Deploy applications to the cluster...'
    credential = docker_ctlr.obtain_credential()
    extra_envs = config_core.get_env()
    lines = API.project.create(base_labels, extra_envs, credential=credential, allow_reuse=False)
    for line in lines:
        if 'stream' in line:
            sys.stdout.write(line['stream'])
        if 'result' in line and line['result'] == 'succeed':
            break

    # Apply ingress for service
    apps = project.get('app', dict())
    ingress = project['ingress']
    for name, value in ingress.items():
        service_name, port = value['target'].split(':')
        if service_name in apps.keys():
            apps[service_name]['ingress'] = {
                'name': name,
                'rewritePath': value['rewritePath'],
                'port': port
            }

    # Create services
    services = []
    for name, value in apps.items():
        value['name'] = name
        value['kind'] = 'App' # TODO to be deleted
        services.append(value)

    yield 'Start services...'
    with interrupt_handler(message='Wait...', blocked=True) as h:
        res = API.service.create(project_key, services)
        if h.interrupted:
            pass

    yield 'Done.'
    yield utils.print_info(f'Project key : {project_key}')

    # Get ingress path for deployed service
    address = config['apiserver']['address'].rsplit(':', 1)[0]
    for service in res:
        if service['ingress']:
            path = f'{address}:{service["ingress_port"]}{service["ingress"]}'
            yield utils.print_info(f'[{service["name"]}] Ingress Path : {path}')


def kill(project_key: str, no_dump: bool):
    return train.down(None, project_key, no_dump)


def scale(scales: List[Tuple[str, int]], project_key: str):
    return train.scale(scales, None, project_key)


def ingress():
    config = config_core.get()
    address = config['apiserver']['address'].rsplit(':', 1)[0]
    services = API.service.get()['inspects']
    rows = [('USERNAME', 'PROJECT NAME', 'APP NAME', 'KEY', 'PATH')]
    for service in services:
        if 'ingress' in service:
            username = service['username']
            project_name = service['project']
            app_name = service['name']
            key = service['key']
            path = f'{address}:{service["ingress_port"]}{service["ingress"]}'
            rows.append((username, project_name, app_name, key, path))
    utils.print_table(rows, 'Cannot find running deployments', 0, False)
