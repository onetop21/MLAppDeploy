import os
import sys
import json
import copy
import socket
import time

from datetime import datetime
from typing import Optional, List, Dict, Tuple, Union
from pathlib import Path
from contextlib import closing
from collections import defaultdict

import yaml
import docker

from dictdiffer import diff

from mlad.cli.libs import utils, interrupt_handler
from mlad.cli.format import PROJECT
from mlad.cli import config as config_core
from mlad.cli.exceptions import (
    ProjectAlreadyExistError, ImageNotFoundError, InvalidProjectKindError,
    MountError, PluginUninstalledError, InvalidUpdateOptionError, ProjectDeletedError,
    MountPortAlreadyUsedError, InvalidDependsError
)
from mlad.core.docker import controller as docker_ctlr
from mlad.core.libs.constants import CONFIG_ENVS, MLAD_PROJECT, MLAD_PROJECT_IMAGE

from mlad.api import API
from mlad.api.exceptions import ProjectNotFound, InvalidLogRequest, NotFound


def init(name, version, maintainer):
    if utils.read_project():
        print('Already generated project file.', file=sys.stderr)
        sys.exit(1)

    if not name:
        name = input('Project Name : ')
    with open(utils.DEFAULT_PROJECT_FILE, 'w') as f:
        f.write(PROJECT.format(
            NAME=name,
            VERSION=version,
            MAINTAINER=maintainer,
        ))


def ls(no_trunc: bool):
    projects = {}
    project_specs = API.project.get()
    app_specs = API.app.get()['specs']
    metrics_server_running = API.check.check_metrics_server()

    if not metrics_server_running:
        yield f'{utils.info_msg("Warning: Metrics server must be installed to load resource information. Please contact the admin.")}'

    columns = [('USERNAME', 'PROJECT', 'KEY', 'APPS',
                'TASKS', 'HOSTNAME', 'WORKSPACE', 'AGE',
                'MEM(Mi)', 'CPU', 'GPU')]
    for spec in project_specs:
        project_key = spec['key']
        default = {
            'username': spec['username'],
            'project': spec['project'],
            'kind': spec['kind'],
            'key': spec['key'],
            'image': spec['image'],
            'apps': 0, 'replicas': 0, 'tasks': 0,
            'hostname': spec['workspace']['hostname'],
            'workspace': spec['workspace']['path'],
            'age': utils.created_to_age(spec['created'])
        }
        projects[project_key] = projects[project_key] \
            if project_key in projects else default
        target_app_specs = [spec for spec in app_specs
                            if spec['key'] == project_key]

        for spec in target_app_specs:
            tasks = spec['task_dict'].values()
            tasks_state = [task['status'] for task in tasks]
            projects[project_key]['apps'] += 1
            projects[project_key]['replicas'] += spec['replicas']
            projects[project_key]['tasks'] += tasks_state.count('Running')

        resource = API.project.resource(project_key, no_trunc=no_trunc)
        projects[project_key].update(resource)

    for project in projects.values():
        run_apps = project['apps'] > 0
        task_info = f'{project["tasks"]}/{project["replicas"]}'
        columns.append((project['username'], project['project'], project['key'],
                        project['apps'] if run_apps else '-',
                        task_info if run_apps else '-',
                        project['hostname'], project['workspace'], project['age'],
                        project['mem'], project['cpu'], project['gpu']))
    utils.print_table(columns, 'Cannot find running projects.', 0 if no_trunc else 32, False)


def status(file: Optional[str], project_key: Optional[str], no_trunc: bool, event: bool):
    utils.process_file(file)
    config = config_core.get()
    if project_key is None:
        project_key = utils.workspace_key()

    # Raise exception if the target project is not found.
    try:
        project = API.project.inspect(project_key=project_key)
        if 'deleted' in project and project['deleted']:
            raise ProjectDeletedError(project['key'])
        apps = API.app.get(project_key)['specs']
        metrics_server_running = API.check.check_metrics_server()
        resources = API.project.resource(project_key, group_by='app', no_trunc=no_trunc) \
            if metrics_server_running else {}
    except NotFound as e:
        raise e

    if not metrics_server_running:
        yield f'{utils.info_msg("Warning: Metrics server must be installed to load resource information. Please contact the admin.")}'

    events = []
    columns = [
        ('NAME', 'APP NAME', 'NODE', 'PHASE', 'STATUS', 'RESTART', 'AGE', 'PORTS', 'MEM(Mi)', 'CPU', 'GPU')]
    for spec in apps:
        task_info = []
        app_name = spec['name']
        try:
            ports = ','.join(map(lambda expose: str(expose['port']), spec['expose']))
            for pod_name, pod in spec['task_dict'].items():
                age = utils.created_to_age(pod['created'])

                if app_name in resources:
                    res = resources[app_name][pod_name]
                else:
                    res = {'cpu': '-', 'gpu': '-', 'mem': '-'}

                task_info.append((
                    pod_name,
                    app_name,
                    pod['node'] if pod['node'] is not None else '-',
                    pod['phase'],
                    pod['status'],
                    pod['restart'],
                    age,
                    ports,
                    res['mem'],
                    res['cpu'],
                    res['gpu']
                ))

                if event and len(pod['events']) > 0:
                    events += pod['events']
        except NotFound:
            pass
        columns += sorted([tuple(elem) for elem in task_info], key=lambda x: x[1])
    username = utils.get_username(config['session'])
    print(f"USERNAME: [{username}] / PROJECT: [{project['project']}]")
    utils.print_table(columns, 'Cannot find running apps.', 0 if no_trunc else 32, False)

    if event:
        sorted_events = sorted(events, key=lambda e: e['datetime'])
        colorkey = {}
        print('\nEVENTS:')
        for event in sorted_events:
            event['timestamp'] = event.pop('datetime')
            event['stream'] = event.pop('message')
            yield _format_log(event, colorkey)


def logs(file: Optional[str], project_key: Optional[str],
         tail: Union[str, int], follow: bool, timestamps: bool, filters: Optional[List[str]]):
    utils.process_file(file)
    if project_key is None:
        project_key = utils.workspace_key()

    # Raise exception if the target project is not found.
    try:
        API.project.inspect(project_key=project_key)
    except NotFound as e:
        raise e

    logs = API.project.log(project_key, tail, follow, timestamps, filters)

    colorkey = {}
    for log in logs:
        if '[Ignored]' in log['stream']:
            continue
        yield _format_log(log, colorkey)


def ingress():
    specs = API.app.get()['specs']

    # check ingress controller
    ingress_ctrl_running = API.check.check_ingress_controller()
    if not ingress_ctrl_running:
        yield f'{utils.info_msg("Warning: Ingress controller must be installed to use ingress path. Please contact the admin.")}'

    rows = [('USERNAME', 'PROJECT NAME', 'APP NAME', 'KEY', 'PORT', 'PATH')]
    for spec in specs:
        username = spec['username']
        project_name = spec['project']
        app_name = spec['name']
        key = spec['key']
        for expose_spec in spec['expose']:
            if 'ingress' in expose_spec:
                port = expose_spec['port']
                path = expose_spec['ingress']['path']
                rows.append((username, project_name, app_name, key, port, path))
    utils.print_table(rows, 'Cannot find running deployments', 0, False)


def edit(file: Optional[str]):
    utils.process_file(file)
    file_path = utils.get_project_file()
    from mlad.cli.editor import run_editor
    run_editor(file_path)


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
    origin_project = copy.deepcopy(project)

    kind = project['kind']
    if not kind == 'Deployment':
        raise InvalidProjectKindError('Deployment', 'deploy')

    base_labels = utils.base_labels(
        utils.get_workspace(),
        config['session'],
        project,
        config_core.get_registry_address(config)
    )

    # Check the project already exists
    project_key = base_labels[MLAD_PROJECT]
    try:
        API.project.inspect(project_key=project_key)
        raise ProjectAlreadyExistError(project_key)
    except ProjectNotFound:
        pass

    # Find suitable image
    image_tag = base_labels[MLAD_PROJECT_IMAGE]
    images = [image for image in docker_ctlr.get_images(project_key=project_key)
              if image_tag in image.tags]
    if len(images) == 0:
        raise ImageNotFoundError(image_tag)

    # check ingress controller
    ingress_ctrl_running = API.check.check_ingress_controller()
    if not ingress_ctrl_running:
        yield f'{utils.info_msg("Warning: Ingress controller must be installed to use ingress path. Please contact the admin.")}'

    # Check app specs
    app_specs = []
    app_dict = project.get('app', dict())
    for name, app_spec in app_dict.items():
        check_nvidia_plugin_installed(app_spec)
        warning_msg = _check_config_envs(name, app_spec)
        if warning_msg:
            yield warning_msg
        app_spec['name'] = name
        app_spec = _convert_tag_only_image_prop(app_spec, image_tag)
        app_spec = _bind_default_values_for_mounts(app_spec, app_specs, images[0])
        app_specs.append(app_spec)

    _validate_depends(app_specs)

    # Create a project
    yield 'Deploy apps to the cluster...'
    credential = docker_ctlr.obtain_credential()
    extra_envs = config_core.get_env()
    lines = API.project.create(base_labels, origin_project, extra_envs,
                               credential=credential)
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
                port = _find_port_from_mount_options(mount)
                yield 'Run NFS server container'
                yield f'  Path: {path}'
                yield f'  Port: {port}'
                try:
                    docker_ctlr.run_nfs_container(project_key, path, port)
                except docker.errors.APIError as e:
                    raise MountError(str(e))

        yield 'Start apps...'

        with interrupt_handler(message='Wait...', blocked=True) as h:
            res = API.app.create(project_key, app_specs)
            if h.interrupted:
                pass
    except Exception as e:
        next(API.project.delete(project_key))
        docker_ctlr.remove_nfs_containers(project_key)
        raise e
    yield 'Done.'
    yield utils.info_msg(f'Project key : {project_key}')

    # Get ingress path for deployed app
    for app in res:
        for expose_spec in app['expose']:
            if 'ingress' in expose_spec:
                yield utils.info_msg(f'Ingress: {expose_spec["ingress"]["path"]} -> {app["name"]}:{expose_spec["port"]}')


def down(file: Optional[str], project_key: Optional[str], dump: bool):
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
        if dump:
            dirpath = _get_log_dirpath(project, project_key_assigned)
            filepath = dirpath / 'description.yml'
            yield utils.info_msg(f'Project Log Storage: {dirpath}')
            if not os.path.isfile(filepath):
                with open(filepath, 'w') as log_file:
                    yaml.dump(project, log_file)
            for app_name in app_names:
                yield _dump_logs(app_name, project_key, dirpath)

        # Remove the apps
        lines = API.app.remove(project_key, apps=app_names)
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


def down_force(file: Optional[str], project_key: Optional[str], dump: bool):
    from mlad.core.kubernetes import controller as k8s_ctlr
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
        if dump:
            dirpath = _get_log_dirpath(project, project_key_assigned)
            filepath = dirpath / 'description.yml'
            yield utils.info_msg(f'Project Log Storage: {dirpath}')
            if not os.path.isfile(filepath):
                with open(filepath, 'w') as log_file:
                    yaml.dump(project, log_file)
            for app_name in app_names:
                yield _dump_logs(app_name, project_key, dirpath)

        # Remove the apps
        k8s_cli = config_core.get_admin_k8s_cli(k8s_ctlr)
        namespace = k8s_ctlr.get_k8s_namespace(project_key, cli=k8s_cli)
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
                                     disconnect_handler=handler, cli=k8s_cli)
        for line in lines:
            if 'stream' in line:
                yield line['stream']
            if 'result' in line and line['result'] == 'stopped':
                break
        handler()

        # Remove the project
        lines = k8s_ctlr.delete_k8s_namespace(namespace, cli=k8s_cli)
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
                log = _format_log(log, pretty=False) + '\n'
                log_file.write(log)
        except InvalidLogRequest:
            return f'There is no log in [{app_name}].'
    return f'The log file of app [{app_name}] saved.'


def run(file: Optional[str], env: Dict[str, str], quota: Dict[str, str], command: List[str]):
    utils.process_file(file)
    config = config_core.get()
    project = utils.get_project()
    origin_project = copy.deepcopy(project)

    base_labels = utils.base_labels(
        utils.get_workspace(),
        config['session'],
        project,
        config_core.get_registry_address(config)
    )
    project_key = base_labels[MLAD_PROJECT]
    try:
        API.project.inspect(project_key=project_key)
        raise ProjectAlreadyExistError(project_key)
    except ProjectNotFound:
        pass

    # Find suitable image
    image_tag = base_labels[MLAD_PROJECT_IMAGE]
    images = [image for image in docker_ctlr.get_images(project_key=project_key)
              if image_tag in image.tags]
    if len(images) == 0:
        raise ImageNotFoundError(image_tag)

    # check ingress controller
    ingress_ctrl_running = API.check.check_ingress_controller()
    if not ingress_ctrl_running:
        yield f'{utils.info_msg("Warning: Ingress controller must be installed to use ingress path. Please contact the admin.")}'

    app_spec = {
        'kind': 'Job',
        'name': 'job-1',
        'env': env,
        'quota': quota,
        'command': command
    }
    check_nvidia_plugin_installed(app_spec)
    warning_msg = _check_config_envs(app_spec['name'], app_spec)
    if warning_msg:
        yield warning_msg
    yield 'Deploy job-1 to the cluster...'
    try:
        credential = docker_ctlr.obtain_credential()
        extra_envs = config_core.get_env()
        lines = API.project.create(base_labels, origin_project, extra_envs,
                                   credential=credential)
        for line in lines:
            if 'stream' in line:
                sys.stdout.write(line['stream'])
            if 'result' in line and line['result'] == 'succeed':
                break

        API.app.create(project_key, [app_spec])

        yield 'Wait for the app runs successfully'
        while True:
            task_dict = API.app.inspect(project_key, app_spec['name'])['task_dict']
            pod_info = list(task_dict.values())[0]
            phase = pod_info['phase']
            reason = pod_info['status']
            if phase == 'Pending':
                time.sleep(1)
            elif phase == 'Succeeded' or phase == 'Running':
                break
            else:
                yield 'Error occurred in running the job..'
                yield f'Reason: {reason}'
                break
        yield from logs(file, project_key, 'all', True, True, None)

        yield from down(file, project_key, False)
        yield 'Done.'
    except KeyboardInterrupt as e:
        next(API.project.delete(project_key))
        raise e
    except Exception as e:
        next(API.project.delete(project_key))
        raise e


def scale(file: Optional[str], project_key: Optional[str], scales: List[Tuple[str, int]]):
    utils.process_file(file)
    if project_key is None:
        project_key = utils.workspace_key()

    project = API.project.inspect(project_key)
    if not project['kind'] == 'Deployment':
        raise InvalidProjectKindError('Deployment', 'scale')

    app_names = [app['name'] for app in API.app.get(project_key)['specs']]

    for target_name, value in scales:
        if target_name in app_names:
            API.app.scale(project_key, target_name, value)
            yield f'Scale updated [{target_name}] = {value}'
        else:
            yield f'Cannot find app [{target_name}] in project [{project_key}].'


def update(file: Optional[str], project_key: Optional[str]):
    utils.process_file(file)
    config = config_core.get()
    if project_key is None:
        project_key = utils.workspace_key()
    project = API.project.inspect(project_key=project_key)
    cur_project_yaml = json.loads(project['project_yaml'])
    cur_image_tag = project['image']

    project = utils.get_project()

    kind = project['kind']
    if not kind == 'Deployment':
        raise InvalidProjectKindError('Deployment', 'deploy')

    base_labels = utils.base_labels(
        utils.get_workspace(),
        config['session'],
        project,
        config_core.get_registry_address(config)
    )
    image_tag = base_labels[MLAD_PROJECT_IMAGE]
    if cur_image_tag != image_tag:
        yield (
            f'Image tag [{cur_image_tag}] and [{image_tag}] are different, '
            f'the base image will be updated to [{image_tag}].'
        )
    default_update_spec = {
        'image': image_tag,
        'command': None,
        'args': None,
        'scale': 1,
        'env': {
            'current': {},
            'update': {}
        },
        'quota': None
    }

    cur_apps = cur_project_yaml['app']
    update_apps = project['app']

    def _validate(key: str):
        if key not in default_update_spec.keys():
            raise InvalidUpdateOptionError(key)

    def _check_env(env_key: Union[str, list] = None):
        # Check env to protect MLAD config
        env_checked = set()
        if isinstance(env_key, list):
            env_checked = set(env_key).intersection(CONFIG_ENVS)
        elif isinstance(env_key, str):
            if env_key in CONFIG_ENVS:
                env_checked.add(env_key)
        return env_checked

    # Get diff from project yaml
    update_specs = []
    diff_keys = {}
    for name, app in cur_apps.items():
        update_app = update_apps[name]
        update_app = _convert_tag_only_image_prop(update_app, image_tag)

        update_spec = copy.deepcopy(default_update_spec)
        for key in update_app:
            if key == 'env':
                update_spec[key]['update'] = update_app['env']
            else:
                update_spec[key] = update_app[key]
        if 'env' in app:
            update_spec['env']['current'] = app['env']
        update_spec['name'] = name

        diff_keys[name] = set()
        diffs = list(diff(app, update_app))
        env_ignored = set()
        for diff_type, key, value in diffs:
            key_list = key.split('.')
            root_key = key_list[0]
            elem_key = key_list[1] if len(key_list) > 1 else None

            if diff_type == 'change':
                _validate(root_key)
                if root_key == 'env':
                    env_ignored.update(_check_env(elem_key))
                diff_keys[name].add(root_key)
            else:
                if root_key != '':
                    _validate(root_key)
                    if root_key == 'env':
                        env_ignored.update(_check_env([_[0] for _ in value]))
                    diff_keys[name].add(root_key)
                else:
                    for root_key, elem in value:
                        _validate(root_key)
                        if root_key == 'env':
                            env_ignored.update(_check_env(list(elem.keys())))
                        diff_keys[name].add(root_key)

        if len(env_ignored) > 0:
            yield utils.info_msg(f"Warning: '{name}' env {env_ignored} "
                                 'will be ignored for MLAD preferences.')

        if len(diff_keys[name]) > 0 or image_tag != cur_image_tag:
            update_specs.append(update_spec)

    for name, keys in diff_keys.items():
        if len(keys) > 0:
            yield f'Update {list(keys)} for app "{name}"...'

    if len(update_specs) > 0:
        API.project.update(project_key, project, update_specs)
        yield 'Done.'
    else:
        yield 'No changes to update.'


def _convert_tag_only_image_prop(app_spec, image_tag):
    if 'image' in app_spec and app_spec['image'].startswith(':'):
        app_spec['image'] = image_tag.rsplit(':', 1)[0] + app_spec['image']
    return app_spec


def _find_free_port(used_ports: set, max_retries=100) -> str:
    for _ in range(max_retries):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            port = str(s.getsockname()[1])
            if port not in used_ports:
                return port
    raise RuntimeError('Cannot found the free port')


def _find_port_from_mount_options(mount) -> Optional[str]:
    # ignore the registered port if a nfs value is assigned
    if 'nfs' in mount:
        return None
    for option in mount.get('options', []):
        if option.startswith('port='):
            return option.replace('port=', '')
    return None


def _bind_default_values_for_mounts(app_spec, app_specs, image):
    if 'mounts' not in app_spec:
        return app_spec

    used_ports = set()
    for spec in app_specs:
        for mount in spec.get('mounts', []):
            port = _find_port_from_mount_options(mount)
            if port is not None:
                used_ports.add(port)

    ip = utils.obtain_my_ip()
    for mount in app_spec['mounts']:
        # Set the server and server path
        if 'nfs' in mount:
            mount['server'], mount['serverPath'] = mount['nfs'].split(':')
        else:
            mount['server'] = ip
            mount['serverPath'] = '/'
            if not mount['path'].startswith('/'):
                mount['path'] = str(Path(utils.get_project_file()).parent / Path(mount['path']))

        # Set the mount path
        if not mount['mountPath'].startswith('/'):
            workdir = image.attrs['Config'].get('WorkingDir', '/workspace')
            mount['mountPath'] = str(Path(workdir) / Path(mount['mountPath']))

        # Set the options
        if 'nfs' not in mount:
            registered_port = _find_port_from_mount_options(mount)
            if registered_port is not None and registered_port in used_ports:
                raise MountPortAlreadyUsedError(registered_port)
            elif registered_port is None:
                free_port = _find_free_port(used_ports)
                used_ports.add(free_port)
                mount['options'].append(f'port={free_port}')
            else:
                used_ports.add(registered_port)

    return app_spec


def _validate_depends(app_specs):
    app_names = [spec['name'] for spec in app_specs]
    dependency_dict = defaultdict(lambda: set())
    for spec in app_specs:
        app_name = spec['name']
        for depend in spec.get('depends', []):
            target_app_name = depend['appName']
            if target_app_name not in app_names:
                raise InvalidDependsError(f'{target_app_name} is not in apps.')
            if app_name in dependency_dict[target_app_name]:
                raise InvalidDependsError(f'{app_name} is already in dependencies of {target_app_name}.')
            dependency_dict[app_name].add(target_app_name)


def _format_log(log, colorkey=None, max_name_width=32, pretty=True):
    msg = log['stream'] if isinstance(log['stream'], str) else log['stream'].decode()

    if log.get('error', False):
        return msg

    name = log['name']
    name_width = min(max_name_width, log.get('name_width', max_name_width))
    if len(name) > name_width:
        name = name[:name_width - 3] + '...'

    timestamp = None
    if 'timestamp' in log:
        dt = datetime.fromisoformat(log['timestamp'])
        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")

    if colorkey is not None:
        colorkey[name] = colorkey[name] if name in colorkey else utils.color_table()[utils.color_index()]
    else:
        colorkey = defaultdict(lambda: '')
    if '\r' in msg:
        msg = msg.split('\r')[-1] + '\n'
    if msg.endswith('\n'):
        msg = msg[:-1]
    if timestamp is not None:
        return f'{colorkey[name]}{name:{name_width}}{utils.CLEAR_COLOR if pretty else ""} [{timestamp}] {msg}'
    else:
        return f'{colorkey[name]}{name:{name_width}}{utils.CLEAR_COLOR if pretty else ""} {msg}'


def _check_config_envs(name: str, app_spec: dict):
    if 'env' in app_spec:
        ignored = set(dict(app_spec['env'])).intersection(CONFIG_ENVS)
        if len(ignored) > 0:
            return utils.info_msg(f"Warning: '{name}' env {ignored} will be ignored for MLAD preferences.")
