import os
import sys
import json

from typing import Optional, Dict
from pathlib import Path

import yaml
import docker

from mlad.cli import config as config_core
from mlad.cli.libs import utils, interrupt_handler
from mlad.cli.exceptions import (
    ProjectAlreadyExistError, ImageNotFoundError, InvalidProjectKindError,
    MountError, PluginUninstalledError
)

from mlad.core.docker import controller as docker_ctlr
from mlad.core.kubernetes import controller as k8s_ctlr
from mlad.core.libs import utils as core_utils

from mlad.api import API
from mlad.api.exceptions import ProjectNotFound, InvalidLogRequest


def check_nvidia_plugin_installed(app_spec: dict):
    if 'quota' in app_spec and 'gpu' in app_spec['quota']:
        nvidia_running = API.check.check_nvidia_device_plugin()
        if not nvidia_running:
            raise PluginUninstalledError('Nvidia device plugin must be installed to use gpu quota. '
                                         'Please contact the admin.')


def up(file: Optional[str]):

    utils.process_file(file)
    config = config_core.get()
    project = utils.get_project()

    kind = project['kind']
    if not kind == 'Train':
        raise InvalidProjectKindError('Train', 'train')

    base_labels = core_utils.base_labels(
        utils.get_workspace(),
        config.session,
        project,
        utils.get_registry_address(config)
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

    # Check app specs
    app_specs = []
    for name, app_spec in project.get('app', dict()).items():
        check_nvidia_plugin_installed(app_spec)
        app_spec['name'] = name
        app_spec = utils.convert_tag_only_image_prop(app_spec, image_tag)
        app_spec = utils.bind_default_values_for_mounts(app_spec, app_specs, images[0])
        app_specs.append(app_spec)

    # Create a project
    yield 'Deploy apps to the cluster...'
    credential = docker_ctlr.obtain_credential()
    extra_envs = config_core.get_env()
    lines = API.project.create(base_labels, project, extra_envs, credential=credential, allow_reuse=False)
    for line in lines:
        if 'stream' in line:
            sys.stdout.write(line['stream'])
        if 'result' in line and line['result'] == 'succeed':
            break

    try:
        # Run NFS server containers
        for app_spec in app_specs:
            for mount in app_spec.get('mounts', []):
                if 'nfs' in mount:
                    continue
                path = mount['path']
                port = utils.find_port_from_mount_options(mount)
                yield 'Run NFS server container'
                yield f'  Path: {path}'
                yield f'  Port: {port}'
                try:
                    docker_ctlr.run_nfs_container(project_key, path, port)
                except docker.errors.APIError as e:
                    raise MountError(str(e))

        yield 'Start apps...'

        with interrupt_handler(message='Wait...', blocked=True) as h:
            API.app.create(project_key, app_specs)
            if h.interrupted:
                pass
    except Exception as e:
        next(API.project.delete(project_key))
        docker_ctlr.remove_nfs_containers(project_key)
        raise e
    yield 'Done.'


def down(file: Optional[str], project_key: Optional[str], no_dump: bool):
    utils.process_file(file)
    project_key_assigned = project_key is not None
    if project_key is None:
        project_key = utils.workspace_key()

    # Check the project already exists
    project = API.project.inspect(project_key=project_key)

    with interrupt_handler(message='Wait...', blocked=False):
        apps = API.app.get(project_key)['specs']
        app_names = [app['name'] for app in apps]

        # Dump logs
        if not no_dump:
            dirpath = _get_log_dirpath(project, project_key_assigned)
            filepath = dirpath / 'description.yml'
            yield utils.print_info(f'Project Log Storage: {dirpath}')
            if not os.path.isfile(filepath):
                with open(filepath, 'w') as log_file:
                    yaml.dump(project, log_file)
            for app_name in app_names:
                yield _dump_logs(app_name, project_key, dirpath)

        # Remove the apps
        lines = API.app.remove(project_key, apps=app_names, stream=True)
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
                yield 'The namespace was successfully removed.'
                break

        # Remove NFS server containers
        docker_ctlr.remove_nfs_containers(project_key)

    yield 'Done.'


def down_force(file: Optional[str], project_key: Optional[str], no_dump: bool):
    utils.process_file(file)
    project_key_assigned = project_key is not None
    if project_key is None:
        project_key = utils.workspace_key()

    # Check the project already exists
    project = API.project.inspect(project_key=project_key)

    with interrupt_handler(message='Wait...', blocked=False):
        apps = API.app.get(project_key)['specs']
        app_names = [app['name'] for app in apps]

        # Dump logs
        if not no_dump:
            dirpath = _get_log_dirpath(project, project_key_assigned)
            filepath = dirpath / 'description.yml'
            yield utils.print_info(f'Project Log Storage: {dirpath}')
            if not os.path.isfile(filepath):
                with open(filepath, 'w') as log_file:
                    yaml.dump(project, log_file)
            for app_name in app_names:
                yield _dump_logs(app_name, project_key, dirpath)

        # Remove the apps
        k8s_cli = k8s_ctlr.get_api_client(context=config_core.get_context())
        namespace = k8s_ctlr.get_namespace(cli=k8s_cli, project_key=project_key)
        if namespace is None:
            raise ProjectNotFound(f'Cannot find project {project_key}')
        namespace_name = namespace.metadata.name
        targets = [k8s_ctlr.get_app(name, namespace_name, cli=k8s_cli) for name in app_names]
        for target in targets:
            k8s_ctlr.check_project_key(project_key, target, cli=k8s_cli)

        class DisconnectHandler:
            def __init__(self):
                self._callbacks = []

            def add_callback(self, callback):
                self._callbacks.append(callback)

            def __call__(self):
                for cb in self._callbacks:
                    cb()

        handler = DisconnectHandler()
        lines = k8s_ctlr.remove_apps(targets, namespace_name,
                                     disconnect_handler=handler, stream=True, cli=k8s_cli)
        for line in lines:
            if 'stream' in line:
                yield line['stream']
            if 'result' in line and line['result'] == 'stopped':
                break
        handler()

        # Remove the project
        lines = k8s_ctlr.remove_namespace(namespace, stream=True, cli=k8s_cli)
        for line in lines:
            if 'stream' in line:
                sys.stdout.write(line['stream'])
            if 'result' in line and line['result'] == 'succeed':
                yield 'The namespace was successfully removed.'
                break
    yield 'Done.'


def _get_log_dirpath(project: Dict, project_key_assigned: bool) -> Path:
    workdir = json.loads(project['project_yaml'])['workdir'] \
        if not project_key_assigned else str(Path().absolute())
    path = Path(f'{workdir}/.logs/{project["created"].replace(":", "-")}')
    path.mkdir(exist_ok=True, parents=True)
    return path


def _dump_logs(app_name: str, project_key: str, dirpath: Path):
    path = dirpath / f'{app_name}.log'
    with open(path, 'w') as log_file:
        try:
            logs = API.project.log(project_key, timestamps=True, names_or_ids=[app_name])
            for log in logs:
                log = utils.parse_log(log)
                log_file.write(log)
        except InvalidLogRequest:
            return f'There is no log in [{app_name}].'
    return f'The log file of app [{app_name}] saved.'
