import os
import sys
import datetime


from typing import Optional, Dict
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
from mlad.api.exceptions import ProjectNotFound


def _process_file(file: Optional[str]):
    if file is not None and not os.path.isfile(file):
        raise FileNotFoundError('Project file is not exist.')
    file = file or os.environ.get(utils.PROJECT_FILE_ENV_KEY, None)
    if file is not None:
        os.environ[utils.PROJECT_FILE_ENV_KEY] = file


def _parse_log(log: Dict, max_name_width: int = 32, len_short_id: int = 20) -> str:
    name = log['name']
    name_width = min(max_name_width, log['name_width'])
    if 'task_id' in log:
        name = f'{name}.{log["task_id"][:len_short_id]}'
        name_width = min(max_name_width, name_width + len_short_id + 1)
    msg = log['stream'] if isinstance(log['stream'], str) else log['stream'].decode()
    timestamp = f'[{log["timestamp"]}]' if 'timestamp' in log else None
    if msg.startswith('Error'):
        return msg
    else:
        if timestamp is not None:
            return f'{timestamp} {name}: {msg}'
        else:
            return f'{name}: {msg}'


def up(file: Optional[str]):

    _process_file(file)
    config = config_core.get()
    project = utils.get_project(default_project)
    project = validators.validate_project(project)

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
    registry_address = _get_registry_address(config)
    image_tag = f'{registry_address}/{image_tag}'
    image.tag(image_tag)
    base_labels['MLAD.PROJECT.IMAGE'] = image_tag

    # Push image
    yield f'Upload the image to the registry [{registry_address}]...'
    docker_ctlr.push_image(project_key, image_tag)

    # Create a project
    yield 'Deploy services to the cluster...'
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
    _process_file(file)
    if project_key is None:
        project_key = utils.project_key(utils.get_workspace())

    def _get_log_dirpath(project: Dict) -> Path:
        workdir = utils.get_project(default_project)['workdir']
        timestamp = str(project['created'])
        time = str(datetime.fromtimestamp(int(timestamp))).replace(':', '-')
        return Path(f'{workdir}/.logs/{time}').mkdir(exist_ok=True, parents=True)

    def _dump_logs(service_name: str, dirpath: Path):
        path = dirpath / f'{service_name}.log'
        with open(path, 'w') as log_file:
            logs = API.project.log(project_key, timestamps=True, names_or_ids=[service_name])
            for log in logs:
                log = _parse_log(log)
                log_file.write(log)
            yield f'The log file of service [{service_name}] saved.'

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
                _dump_logs(service_name, dirpath)

        # Remove the services
        for service in services:
            lines = API.service.remove(project_key, services=service_names, stream=True)
            for line in lines:
                if 'stream' in line:
                    sys.stdout.write(line['stream'])
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
