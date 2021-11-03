import os
import sys

from datetime import datetime
from typing import Optional, Dict, List, Tuple
from pathlib import Path

import yaml

from mlad.cli import config as config_core
from mlad.cli import context
from mlad.cli.libs import utils, interrupt_handler
from mlad.cli.validator import validators
from mlad.cli.exceptions import (
    ProjectAlreadyExistError, ImageNotFoundError
)

from mlad.core.docker import controller2 as docker_ctlr
from mlad.core.default import project as default_project
from mlad.core.libs import utils as core_utils

from mlad.api import API
from mlad.api.exceptions import ProjectNotFound, InvalidLogRequest


def up(file: Optional[str]):

    utils.process_file(file)
    config = config_core.get()
    project = utils.get_project(default_project)
    project = validators.validate(project)

    kind = project['kind']
    if not kind == 'Train':
        raise InvalidProjectKindError('Deployment', 'deploy')

    base_labels = core_utils.base_labels(
        utils.get_workspace(),
        config.session,
        project
    )

    # Check the project already exists
    project_key = base_labels['MLAD.PROJECT']
    try:
        API.project.inspect(project_key=project_key)
        raise ProjectAlreadyExistError(project_key)
    except ProjectNotFound:
        pass

    # Find suitable image
    image_tag = base_labels['MLAD.PROJECT.IMAGE']
    images = [image for image in docker_ctlr.get_images(project_key=project_key)
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

    # Create services
    services = []
    for name, value in project.get('app', dict()).items():
        value['name'] = name
        services.append(value)

    yield 'Start services...'
    with interrupt_handler(message='Wait...', blocked=True) as h:
        API.service.create(project_key, services)
        if h.interrupted:
            pass

    yield 'Done.'


def down(file: Optional[str], project_key: Optional[str], no_dump: bool):
    utils.process_file(file)
    project_key_assigned = project_key is not None
    if project_key is None:
        project_key = utils.project_key(utils.get_workspace())

    def _get_log_dirpath(project: Dict) -> Path:
        workdir = utils.get_project(default_project)['workdir'] \
            if not project_key_assigned else str(Path().absolute())
        timestamp = str(project['created'])
        time = str(datetime.fromtimestamp(int(timestamp))).replace(':', '-')
        path = Path(f'{workdir}/.logs/{time}')
        path.mkdir(exist_ok=True, parents=True)
        return path

    def _dump_logs(service_name: str, dirpath: Path):
        path = dirpath / f'{service_name}.log'
        with open(path, 'w') as log_file:
            try:
                logs = API.project.log(project_key, timestamps=True, names_or_ids=[service_name])
                for log in logs:
                    log = _parse_log(log)
                    log_file.write(log)
            except InvalidLogRequest:
                return f'There is no log in [{service_name}].'
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


def scale(scales: List[Tuple[str, int]], file: Optional[str], project_key: Optional[str]):
    utils.process_file(file)
    if project_key is None:
        project_key = utils.project_key(utils.get_workspace())

    API.project.inspect(project_key)

    service_names = [service['name'] for service in API.service.get(project_key)['inspects']]

    for target_name, value in scales:
        if target_name in service_names:
            API.service.scale(project_key, target_name, value)
            yield f'Scale updated [{target_name}] = {value}'
