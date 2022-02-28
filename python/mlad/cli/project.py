import os
import sys
import json
import copy
import datetime

from typing import Optional, List, Dict, Tuple, Union
from pathlib import Path

import yaml
import docker

from dictdiffer import diff

from mlad.cli.libs import utils, interrupt_handler
from mlad.cli.format import PROJECT
from mlad.cli import config as config_core
from mlad.cli.exceptions import (
    ProjectAlreadyExistError, ImageNotFoundError, InvalidProjectKindError,
    MountError, PluginUninstalledError, InvalidUpdateOptionError, ProjectDeletedError
)
from mlad.core.docker import controller as docker_ctlr
from mlad.core.kubernetes import controller as k8s_ctlr
from mlad.core.libs import utils as core_utils

from mlad.api import API
from mlad.api.exceptions import ProjectNotFound, InvalidLogRequest, NotFound


config_envs = {'APP', 'AWS_ACCESS_KEY_ID', 'AWS_REGION', 'AWS_SECRET_ACCESS_KEY', 'DB_ADDRESS',
               'DB_PASSWORD', 'DB_USERNAME', 'MLAD_ADDRESS', 'MLAD_SESSION', 'PROJECT',
               'PROJECT_ID', 'PROJECT_KEY', 'S3_ENDPOINT', 'S3_USE_HTTPS', 'S3_VERIFY_SSL',
               'USERNAME'}


def check_config_envs(name: str, app_spec: dict):
    if 'env' in app_spec:
        ignored = set(dict(app_spec['env'])).intersection(config_envs)
        if len(ignored) > 0:
            return utils.print_info(f"Warning: '{name}' env {ignored} will be ignored for MLAD preferences.")


def _parse_log(log, max_name_width=32, len_short_id=10):
    name = log['name']
    namewidth = min(max_name_width, log['name_width'])if 'name_width' in log else max_name_width
    if 'task_id' in log:
        name = f"{name}.{log['task_id'][:len_short_id]}"
        namewidth = min(max_name_width, namewidth + len_short_id + 1)
    if len(name) > max_name_width:
        name = name[:max_name_width - 3] + '...'

    msg = log['stream'] if isinstance(log['stream'], str) else log['stream'].decode()

    dt = None
    if 'timestamp' in log:
        timestamp = f'{log["timestamp"]}'
        dt = datetime.datetime.fromisoformat(timestamp) + datetime.timedelta(hours=9)
        dt = f'[{dt.strftime("%Y-%m-%d %H:%M:%S")}]'
    return name, namewidth, msg, dt


def _print_log(log, colorkey, max_name_width=32, len_short_id=10):
    name, namewidth, msg, timestamp = _parse_log(log, max_name_width, len_short_id)
    if msg.startswith('Error'):
        sys.stderr.write(f'{utils.ERROR_COLOR}{msg}{utils.CLEAR_COLOR}')
    else:
        colorkey[name] = colorkey[name] if name in colorkey else utils.color_table()[utils.color_index()]
        if '\r' in msg:
            msg = msg.split('\r')[-1] + '\n'
        if not msg.endswith('\n'):
            msg += '\n'
        if timestamp:
            sys.stdout.write(("{}{:%d}{} {} {}" % namewidth).format(colorkey[name], name, utils.CLEAR_COLOR, timestamp, msg))
        else:
            sys.stdout.write(("{}{:%d}{} {}" % namewidth).format(colorkey[name], name, utils.CLEAR_COLOR, msg))


def _get_default_logs(log):
    name, _, msg, timestamp = _parse_log(log, len_short_id=20)
    if msg.startswith('Error'):
        return msg
    else:
        if timestamp:
            return f'{timestamp} {name}: {msg}'
        else:
            return f'{name}: {msg}'


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
    metrics_server_running = API.check.check_metrics_server()

    if not metrics_server_running:
        yield f'{utils.print_info("Warning: Metrics server must be installed to load resource information. Please contact the admin.")}'

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
        apps = API.app.get(project_key=project_key)

        for spec in apps['specs']:
            tasks = spec['tasks'].values()
            tasks_state = [_['status']['state'] for _ in tasks]
            projects[project_key]['apps'] += 1
            projects[project_key]['replicas'] += spec['replicas']
            projects[project_key]['tasks'] += tasks_state.count('Running')

        if metrics_server_running:
            used = {'cpu': 0, 'gpu': 0, 'mem': 0}
            resources = API.project.resource(project_key)
            for tasks in resources.values():
                for resource in tasks.values():
                    used['mem'] += resource['mem'] if resource['mem'] is not None else 0
                    used['cpu'] += resource['cpu'] if resource['cpu'] is not None else 0
                    used['gpu'] += resource['gpu'] if resource['gpu'] is not None else 0
            for k in used:
                used[k] = used[k] if no_trunc else round(used[k], 1)
        else:
            used = {'cpu': '-', 'gpu': '-', 'mem': '-'}

        projects[project_key].update(used)

    for project in projects.values():
        if project['apps'] > 0:
            running_tasks = f"{project['tasks']}/{project['replicas']}"
            columns.append((project['username'], project['project'], project['key'],
                            project['apps'], f"{running_tasks:>5}", project['hostname'],
                            project['workspace'], project['age'],
                            project['mem'], project['cpu'], project['gpu']))
        else:
            columns.append((project['username'], project['project'], project['key'],
                            '-', '-', project['hostname'],
                            project['workspace'], project['age'],
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
        if metrics_server_running:
            resources = API.project.resource(project_key)
    except NotFound as e:
        raise e

    if not metrics_server_running:
        yield f'{utils.print_info("Warning: Metrics server must be installed to load resource information. Please contact the admin.")}'

    events = []
    columns = [
        ('NAME', 'APP NAME', 'NODE', 'PHASE', 'STATUS', 'RESTART', 'AGE', 'PORTS', 'MEM(Mi)', 'CPU', 'GPU')]
    for spec in apps:
        task_info = []
        app_name = spec['name']
        try:
            ports = ','.join(map(str, spec['ports']))
            for pod_name, pod in spec['tasks'].items():
                ready_cnt = 0
                restart_cnt = 0
                if pod['container_status']:
                    for _ in pod['container_status']:
                        restart_cnt += _['restart']
                        if _['ready']:
                            ready_cnt += 1

                age = utils.created_to_age(pod['created'])

                if metrics_server_running and app_name in resources:
                    res = resources[app_name][pod_name].copy()
                    res['mem'] = 'NotReady' if res['mem'] is None else round(res['mem'], 1)
                    res['cpu'] = 'NotReady' if res['cpu'] is None else round(res['cpu'], 1)
                    res['gpu'] = 'NotReady' if res['gpu'] is None else res['gpu']
                else:
                    res = {'cpu': '-', 'gpu': '-', 'mem': '-'}

                task_info.append((
                    pod_name,
                    app_name,
                    pod['node'] if pod['node'] else '-',
                    pod['phase'],
                    'Running' if pod['status']['state'] == 'Running' else
                    pod['status']['detail']['reason'],
                    restart_cnt,
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
    username = utils.get_username(config.session)
    print(f"USERNAME: [{username}] / PROJECT: [{project['project']}]")
    utils.print_table(columns, 'Cannot find running apps.', 0 if no_trunc else 32, False)

    if event:
        sorted_events = sorted(events, key=lambda e: e['datetime'])
        colorkey = {}
        print('\nEVENTS:')
        for event in sorted_events:
            event['timestamp'] = event.pop('datetime')
            event['stream'] = event.pop('message')
            _print_log(event, colorkey, 32, 20)


def logs(file: Optional[str], project_key: Optional[str],
         tail: bool, follow: bool, timestamps: bool, names_or_ids: List[str]):
    utils.process_file(file)
    if project_key is None:
        project_key = utils.workspace_key()

    # Raise exception if the target project is not found.
    try:
        API.project.inspect(project_key=project_key)
    except NotFound as e:
        raise e

    logs = API.project.log(project_key, tail, follow, timestamps, names_or_ids)

    colorkey = {}
    for log in logs:
        if '[Ignored]' in log['stream']:
            continue
        _print_log(log, colorkey, 32, 20)


def ingress():
    specs = API.app.get()['specs']

    # check ingress controller
    ingress_ctrl_running = API.check.check_ingress_controller()
    if not ingress_ctrl_running:
        yield f'{utils.print_info("Warning: Ingress controller must be installed to use ingress path. Please contact the admin.")}'

    rows = [('USERNAME', 'PROJECT NAME', 'APP NAME', 'KEY', 'PORT', 'PATH')]
    for spec in specs:
        username = spec['username']
        project_name = spec['project']
        app_name = spec['name']
        key = spec['key']
        for ingress in spec['ingress']:
            port = ingress['port']
            path = ingress['path']
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

    # check ingress controller
    ingress_ctrl_running = API.check.check_ingress_controller()
    if not ingress_ctrl_running:
        yield f'{utils.print_info("Warning: Ingress controller must be installed to use ingress path. Please contact the admin.")}'

    # Check app specs
    app_specs = []
    app_dict = project.get('app', dict())
    for name, app_spec in app_dict.items():
        check_nvidia_plugin_installed(app_spec)
        warning_msg = check_config_envs(name, app_spec)
        if warning_msg:
            yield warning_msg
        app_spec['name'] = name
        app_spec = utils.convert_tag_only_image_prop(app_spec, image_tag)
        app_spec = utils.bind_default_values_for_mounts(app_spec, app_specs, images[0])
        app_specs.append(app_spec)

    utils.validate_depends(app_specs)

    # Create a project
    yield 'Deploy apps to the cluster...'
    credential = docker_ctlr.obtain_credential()
    extra_envs = config_core.get_env()
    lines = API.project.create(base_labels, origin_project, extra_envs,
                               credential=credential, allow_reuse=False)
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
            res = API.app.create(project_key, app_specs)
            if h.interrupted:
                pass
    except Exception as e:
        next(API.project.delete(project_key))
        docker_ctlr.remove_nfs_containers(project_key)
        raise e
    yield 'Done.'
    yield utils.print_info(f'Project key : {project_key}')

    # Get ingress path for deployed app
    for app in res:
        if len(app['ingress']) > 0:
            yield utils.print_info(f'[{app["name"]}] Ingress Path :')
            for ingress in app['ingress']:
                yield utils.print_info(f'- port: {ingress["port"]} -> {ingress["path"]}')


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


def down_force(file: Optional[str], project_key: Optional[str], dump: bool):
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
    if project_key is None:
        project_key = utils.workspace_key()
    project = API.project.inspect(project_key=project_key)
    cur_project_yaml = json.loads(project['project_yaml'])
    image_tag = project['image']

    project = utils.get_project()

    kind = project['kind']
    if not kind == 'Deployment':
        raise InvalidProjectKindError('Deployment', 'deploy')

    default_update_spec = {
        'image': None,
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
            env_checked = set(env_key).intersection(config_envs)
        elif isinstance(env_key, str):
            if env_key in config_envs:
                env_checked.add(env_key)
        return env_checked

    # Get diff from project yaml
    update_specs = []
    diff_keys = {}
    for name, app in cur_apps.items():
        update_app = update_apps[name]
        update_app = utils.convert_tag_only_image_prop(update_app, image_tag)

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
            yield utils.print_info(f"Warning: '{name}' env {env_ignored} "
                                   f"will be ignored for MLAD preferences.")

        if len(diff_keys[name]) > 0:
            update_specs.append(update_spec)

    for name, keys in diff_keys.items():
        if len(keys) > 0:
            yield f'Update {list(keys)} for app "{name}"...'

    if len(update_specs) > 0:
        API.project.update(project_key, project, update_specs)
        yield 'Done.'
    else:
        yield 'No changes to update.'
