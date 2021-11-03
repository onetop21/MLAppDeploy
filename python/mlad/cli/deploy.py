import os
import sys

from datetime import datetime
from typing import Optional, Dict
from pathlib import Path

import yaml

from mlad.cli import config as config_core
from mlad.cli import context
from mlad.cli.libs import utils, interrupt_handler
from mlad.cli.validator import validators
from mlad.cli.exceptions import (
    ProjectAlreadyExistError, ImageNotFoundError, InvalidProjectKindError
)

from mlad.core.docker import controller2 as docker_ctlr
from mlad.core.default import project as default_project
from mlad.core.libs import utils as core_utils

from mlad.api import API
from mlad.api.exceptions import ProjectNotFound


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
    registry_address = _get_registry_address(config)
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
        API.service.create(project_key, services)
        if h.interrupted:
            pass

    yield 'Done.'
    yield f'Project key : {project_key}'


def kill(project_key: str, no_dump: bool):

    def _get_log_dirpath(project: Dict) -> Path:
        workdir = str(Path().absolute())
        timestamp = str(project['created'])
        time = str(datetime.fromtimestamp(int(timestamp))).replace(':', '-')
        path = Path(f'{workdir}/.logs/{time}')
        path.mkdir(exist_ok=True, parents=True)
        return path

    def _dump_logs(service_name: str, dirpath: Path):
        path = dirpath / f'{service_name}.log'
        with open(path, 'w') as log_file:
            logs = API.project.log(project_key, timestamps=True, names_or_ids=[service_name])
            for log in logs:
                log = utils.parse_log(log)
                log_file.write(log)
            return f'The log file of service [{service_name}] saved.'

    # Check the project already exists
    project = API.project.inspect(project_key=project_key)

    with interrupt_handler(message='Wait...', blocked=False):
        services = API.service.get(project_key)['inspects']
        service_names = [service['name'] for service in services]

        # Dump logs
        if not no_dump:
            dirpath = _get_log_dirpath(project)
            filepath = dirpath / 'description.yml'
            yield f'{utils.INFO_COLOR}Project Log Storage: {dirpath}{utils.CLEAR_COLOR}'
            if not os.path.isfile(filepath):
                project['created'] = datetime.fromtimestamp(project['created'])
                with open(filepath, 'w') as log_file:
                    yaml.dump(project, log_file)
            for service_name in service_names:
                yield _dump_logs(service_name, dirpath)

        # Remove the services
        lines = API.service.remove(project_key, services=service_names, stream=True)
        for line in lines:
            if 'stream' in line:
                yield line['stream']
            if 'result' in line and line['result'] == 'stopped':
                break

        # Remove the project
        lines = API.project.delete(project_key)
        for line in lines:
            if 'stream' in line:
                sys.stdout.write(line['stream'])
            if 'result' in line and line['result'] == 'succeed':
                yield 'The project network was successfully removed.'
                break
    yield 'Done.'


def _get_registry_address(config: context.Context):
    parsed = utils.parse_url(config.docker.registry.address)
    registry_address = parsed['address']
    namespace = config.docker.registry.namespace
    if namespace is not None:
        registry_address += f'/{namespace}'
    return registry_address