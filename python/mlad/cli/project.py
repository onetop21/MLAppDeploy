import sys
import os
import time
import json

from typing import Optional, List
from datetime import datetime
from dateutil import parser

import yaml
import base64
import docker

from mlad.core.docker import controller as ctlr
from mlad.core.kubernetes import controller as k8s_ctlr
from mlad.core.default import project as default_project
from mlad.core.libs import utils as core_utils
from mlad.core import exceptions
from mlad.cli.image import build as project_build
from mlad.cli.libs import utils
from mlad.cli.libs import interrupt_handler
from mlad.cli.Format import PROJECT
from mlad.cli import config as config_core
from mlad.api import API
from mlad.api.exceptions import APIError, NotFound

from mlad.cli.validator import validators
from mlad.cli.validator.exceptions import InvalidProjectYaml
from mlad.cli.exceptions import ImageNotFoundError


def _parse_log(log, max_name_width=32, len_short_id=10):
    name = log['name']
    namewidth = min(max_name_width, log['name_width'])
    if 'task_id' in log:
        name = f"{name}.{log['task_id'][:len_short_id]}"
        namewidth = min(max_name_width, namewidth + len_short_id + 1)
    msg = log['stream'] if isinstance(log['stream'], str) else log['stream'].decode()
    timestamp = f'[{log["timestamp"]}]' if 'timestamp' in log else None
    return name, namewidth, msg, timestamp


def _print_log(log, colorkey, max_name_width=32, len_short_id=10):
    name, namewidth, msg, timestamp = _parse_log(log, max_name_width, len_short_id)
    if msg.startswith('Error'):
        sys.stderr.write(f'{utils.ERROR_COLOR}{msg}{utils.CLEAR_COLOR}')
    else:
        colorkey[name] = colorkey[name] if name in colorkey else utils.color_table()[utils.color_index()]
        if '\r' in msg:
            msg = msg.split('\r')[-1] + '\n'
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


# Main CLI Functions
def init(name, version, maintainer):
    if utils.read_project():
        print('Already generated project file.', file=sys.stderr)
        sys.exit(1)

    if not name:
        name = input('Project Name : ')
    # if not version: version = input('Project Version : ')
    # if not author: author = input('Project Author : ')

    with open(utils.DEFAULT_PROJECT_FILE, 'w') as f:
        f.write(PROJECT.format(
            NAME=name,
            VERSION=version,
            MAINTAINER=maintainer,
        ))


def list(no_trunc: bool):
    projects = {}
    networks = API.project.get()

    columns = [('USERNAME', 'PROJECT', 'KIND', 'KEY', 'IMAGE',
                'SERVICES', 'TASKS', 'HOSTNAME', 'WORKSPACE',
                'MEM(Mi)', 'CPU', 'GPU')]
    for network in networks:
        project_key = network['key']
        default = {
            'username': network['username'],
            'project': network['project'],
            'kind': network['kind'],
            'key': network['key'],
            'image': network['image'],
            'services': 0, 'replicas': 0, 'tasks': 0,
            'hostname': network['workspace']['hostname'],
            'workspace': network['workspace']['path'],
        }
        projects[project_key] = projects[project_key] \
            if project_key in projects else default
        services = API.service.get(project_key=project_key)

        for inspect in services['inspects']:
            tasks = inspect['tasks'].values()
            tasks_state = [_['status']['state'] for _ in tasks]
            projects[project_key]['services'] += 1
            projects[project_key]['replicas'] += inspect['replicas']
            projects[project_key]['tasks'] += tasks_state.count('Running')

        used = {'cpu': 0, 'gpu': 0, 'mem': 0}
        resources = API.project.resource(project_key)
        for service, resource in resources.items():
            used['mem'] += resource['mem'] if resource['mem'] is not None else 0
            used['cpu'] += resource['cpu'] if resource['cpu'] is not None else 0
            used['gpu'] += resource['gpu']
        for k in used:
            used[k] = used[k] if no_trunc else round(used[k], 1)

        projects[project_key].update(used)

    for project in projects.values():
        if project['services'] > 0:
            running_tasks = f"{project['tasks']}/{project['replicas']}"
            columns.append((project['username'], project['project'],
                            project['kind'], project['key'],
                            project['image'], project['services'],
                            f"{running_tasks:>5}", project['hostname'],
                            project['workspace'], project['mem'],
                            project['cpu'], project['gpu']))
        else:
            columns.append((project['username'], project['project'],
                            project['kind'], project['key'],
                            project['image'], '-', '-', project['hostname'],
                            project['workspace'], project['mem'],
                            project['cpu'], project['gpu']))
    utils.print_table(columns, 'Cannot find running projects.', 0 if no_trunc else 32, False)


def status(file: Optional[str], project_key: Optional[str], all: bool, no_trunc: bool):
    utils.process_file(file)
    config = config_core.get()
    if project_key is None:
        project_key = utils.project_key(utils.get_workspace())
    # Block not running.
    try:
        inspect = API.project.inspect(project_key=project_key)
        resources = API.project.resource(project_key)
    except NotFound:
        print('Cannot find running project.', file=sys.stderr)
        sys.exit(1)

    res = API.service.get(project_key)
    columns = [
        ('NAME', 'SERVICE', 'NODE', 'PHASE', 'STATUS', 'RESTART', 'AGE', 'PORTS', 'MEM(Mi)', 'CPU', 'GPU')]
    for inspect in res['inspects']:
        task_info = []
        try:
            ports = [*inspect['ports']][0] if inspect['ports'] else '-'
            for pod_name, pod in API.service.get_tasks(project_key, inspect['name']).items():
                ready_cnt = 0
                restart_cnt = 0
                if pod['container_status']:
                    for _ in pod['container_status']:
                        restart_cnt += _['restart']
                        if _['ready']:
                            ready_cnt += 1

                uptime = (datetime.utcnow() - parser.parse(pod['created']).
                          replace(tzinfo=None)).total_seconds()
                if uptime > 24 * 60 * 60:
                    uptime = f"{uptime // (24 * 60 * 60):.0f} days"
                elif uptime > 60 * 60:
                    uptime = f"{uptime // (60 * 60):.0f} hours"
                elif uptime > 60:
                    uptime = f"{uptime // 60:.0f} minutes"
                else:
                    uptime = f"{uptime:.0f} seconds"

                res = resources[inspect['name']].copy()
                if res['mem'] is None:
                    res['mem'], res['cpu'] = 'NotReady', 'NotReady'
                    res['gpu'] = round(res['gpu'], 1) \
                        if not no_trunc else res['gpu']
                else:
                    if not no_trunc:
                        res['mem'] = round(res['mem'], 1)
                        res['cpu'] = round(res['cpu'], 1)
                        res['gpu'] = round(res['gpu'], 1)

                if all or pod['phase'] not in ['Failed']:
                    task_info.append((
                        pod_name,
                        inspect['name'],
                        pod['node'] if pod['node'] else '-',
                        pod['phase'],
                        'Running' if pod['status']['state'] == 'Running' else
                        pod['status']['detail']['reason'],
                        restart_cnt,
                        uptime,
                        ports,
                        res['mem'],
                        res['cpu'],
                        res['gpu']
                    ))
        except NotFound:
            pass
        columns += sorted([tuple(elem) for elem in task_info], key=lambda x: x[1])
    username = utils.get_username(config.session)
    print(f"USERNAME: [{username}] / PROJECT: [{inspect['project']}]")
    utils.print_table(columns, 'Cannot find running services.', 0 if no_trunc else 32, False)


def run(no_build, env, quota, command):
    SERVICE_NAME = 'run-app'
    # TBD : option or static value
    timeout = 0xFFFF

    if not no_build:
        project_build(False, False, False)

    envs = dict(os.environ) if env else {}

    quota = {_.split('=')[0]: _.split('=')[1] for _ in quota} if quota else {}
    for k, v in quota.items():
        quota[k] = int(v) if k == 'cpu' or k == 'gpu' else v

    command = [_ for _ in command] if command else []

    config = config_core.get()
    cli = ctlr.get_api_client()
    api = API(config.apiserver.address, config.session)

    project = utils.get_project(default_project)
    try:
        project = validators.validate(project)
    except InvalidProjectYaml as e:
        print('Errors:', e)
        sys.exit(1)

    base_labels = core_utils.base_labels(
        utils.get_workspace(),
        config.session,
        project)

    project_key = base_labels['MLAD.PROJECT']

    try:
        inspect = api.project.inspect(project_key=project_key)
        if inspect:
            print('Failed to create project : Already exist project.')
            sys.exit(1)
    except NotFound:
        pass

    images = ctlr.get_images(cli, project_key=project_key)
    images = [_ for _ in images if base_labels['MLAD.PROJECT.IMAGE'] in _.tags]

    # select suitable image
    if not images:
        print(f"Cannot find built image of project [{project['project']['name']}].",
              file=sys.stderr)
        return
    image = images[0]
    repository = image.labels['MLAD.PROJECT.IMAGE']
    inspect = ctlr.inspect_image(image)

    # set prefix to image name
    parsed_url = utils.parse_url(config.docker.registry.address)
    registry = parsed_url['address']
    if config.docker.registry.namespace:
        registry = f"{registry}/{config.docker.registry.namespace}"
    full_repository = f"{registry}/{repository}"
    image.tag(full_repository)
    base_labels['MLAD.PROJECT.IMAGE'] = full_repository

    # Upload Image
    print('Update project image to registry...')
    try:
        for _ in ctlr.push_image(cli, full_repository, stream=True):
            if 'error' in _:
                raise docker.errors.APIError(_['error'], None)
            elif 'stream' in _:
                sys.stdout.write(_['stream'])
    except docker.errors.APIError as e:
        print(e, file=sys.stderr)
        print('Failed to Update Image to Registry.', file=sys.stderr)
        print('Please Check Registry Server.', file=sys.stderr)
        sys.exit(1)
    except StopIteration:
        pass

    # AuthConfig
    cli = ctlr.get_api_client()
    headers = {'auths': json.loads(base64.urlsafe_b64decode(ctlr.get_auth_headers(cli)['X-Registry-Config'] or b'e30K'))}
    encoded = base64.urlsafe_b64encode(json.dumps(headers).encode())
    credential = encoded.decode()

    extra_envs = config_core.get_env()

    res = api.project.create(base_labels, extra_envs, credential=credential, allow_reuse=True)
    try:
        for _ in res:
            if 'stream' in _:
                sys.stdout.write(_['stream'])
            if 'result' in _:
                if _['result'] == 'succeed':
                    break
    except APIError as e:
        print(e)
        sys.exit(1)

    service = {
        'kind': 'App',
        'name': SERVICE_NAME,
        'command': command,
        'env': envs,
        'quota': quota
    }

    with interrupt_handler(message='Wait.', blocked=True) as h:
        try:
            instance = api.service.create(project_key, [service])[0]
            name = instance['name']
            inspect = api.service.inspect(project_key, name)
            print(f"Starting \'{name}\'...")
            time.sleep(1)
        except APIError as e:
            print(e)
        if h.interrupted:
            pass

    for tick in range(timeout):
        tasks = api.service.get_tasks(project_key, name)
        phase = [tasks[_]['phase'] for _ in tasks][0]
        if phase == 'Running' or phase == 'Succeeded':
            break
        else:
            padding = '\033[1A\033[K' if tick else ''
            sys.stdout.write(f"{padding}Wait service to be running...[{tick}s]\n")
            time.sleep(1)

    logs('all', True, True, SERVICE_NAME)
    down(None, True)


def up():
    config = config_core.get()
    cli = ctlr.get_api_client()
    project = utils.get_project(default_project)
    project = validators.validate(project)

    base_labels = core_utils.base_labels(
        utils.get_workspace(),
        config.session,
        project)

    project_key = base_labels['MLAD.PROJECT']

    try:
        inspect = API.project.inspect(project_key=project_key)
        if inspect:
            print('Failed to create project : Already exist project.')
            sys.exit(1)
    except NotFound:
        pass

    images = ctlr.get_images(cli, project_key=project_key)
    images = [_ for _ in images if base_labels['MLAD.PROJECT.IMAGE'] in _.tags]

    # select suitable image
    if not images:
        raise ImageNotFoundError(project['name'])

    image = images[0]
    repository = image.labels['MLAD.PROJECT.IMAGE']
    inspect = ctlr.inspect_image(image)

    # set prefix to image name
    parsed_url = utils.parse_url(config.docker.registry.address)
    registry = parsed_url['address']
    if config.docker.registry.namespace:
        registry = f"{registry}/{config.docker.registry.namespace}"
    full_repository = f"{registry}/{repository}"
    image.tag(full_repository)
    base_labels['MLAD.PROJECT.IMAGE'] = full_repository

    # Upload Image
    print('Update project image to registry...')
    try:
        for _ in ctlr.push_image(cli, full_repository, stream=True):
            if 'error' in _:
                raise docker.errors.APIError(_['error'], None)
            elif 'stream' in _:
                sys.stdout.write(_['stream'])
    except docker.errors.APIError as e:
        print(e, file=sys.stderr)
        print('Failed to Update Image to Registry.', file=sys.stderr)
        print('Please Check Registry Server.', file=sys.stderr)
        sys.exit(1)
    except StopIteration:
        pass

    print('Deploying services to cluster...')
    targets = project['app'] or {}

    if 'ingress' in project:
        ingress = project['ingress']
        for name, _ in ingress.items():
            service, port = _['target'].split(':')
            if service in targets.keys():
                targets[service]['ingress'] = {
                    'name': name,
                    'rewritePath': _['rewritePath'],
                    'port': port
                }

    # AuthConfig
    cli = ctlr.get_api_client()
    headers = {'auths': json.loads(base64.urlsafe_b64decode(ctlr.get_auth_headers(cli)['X-Registry-Config'] or b'e30K'))}
    encoded = base64.urlsafe_b64encode(json.dumps(headers).encode())
    credential = encoded.decode()

    extra_envs = config_core.get_env()

    res = API.project.create(base_labels, extra_envs,
                             credential=credential, allow_reuse=False)
    try:
        for _ in res:
            if 'stream' in _:
                sys.stdout.write(_['stream'])
            if 'result' in _:
                if _['result'] == 'succeed':
                    break
    except APIError as e:
        print(e)
        sys.exit(1)

    # Check service status
    running_services = API.service.get(project_key)['inspects']
    excludes = []
    for service_name in targets:
        running_svc_names = [_['name'] for _ in running_services]
        if service_name in running_svc_names:
            print(f'Already running service[{service_name}] in project.', file=sys.stderr)
            excludes.append(service_name)
    for _ in excludes:
        del targets[_]

    def _target_model(targets):
        services = []
        for k, v in targets.items():
            v['name'] = k
            services.append(v)
        return services

    target_model = _target_model(targets)

    with interrupt_handler(message='Wait.', blocked=True) as h:
        target_model = _target_model(targets)
        try:
            instances = API.service.create(project_key, target_model)
            for instance in instances:
                name = instance['name']
                inspect = API.service.inspect(project_key, name)
                print(f"Starting \'{name}\'...")
                time.sleep(1)
        except APIError as e:
            print(e)
        if h.interrupted:
            pass

    print('Done.')


def down(no_dump):
    project_key = utils.project_key(utils.get_workspace())
    workdir = utils.get_project(default_project)['workdir']

    # Block duplicated running.
    try:
        inspect = API.project.inspect(project_key=project_key)
    except NotFound:
        print('Already stopped project.', file=sys.stderr)
        sys.exit(1)

    def _get_log_path():
        timestamp = str(inspect['created'])
        time = str(datetime.fromtimestamp(int(timestamp))).replace(':', '-')
        log_dir = f'{workdir}/.logs/{time}'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        return log_dir

    def dump_logs(service, log_dir):
        path = f'{log_dir}/{service}.log'
        with open(path, 'w') as f:
            try:
                logs = API.project.log(project_key, timestamps=True, names_or_ids=[service])
                for _ in logs:
                    log = _get_default_logs(_)
                    f.write(log)
                print(f'Service \'{service}\' log saved.')
            except NotFound:
                print(f'Cannot get logs of pending service \'{service}\'.')

    with interrupt_handler(message='Wait.', blocked=False):
        running_services = API.service.get(project_key)['inspects']
        targets = [(_['id'], _['name']) for _ in running_services]

        # Save desc & log
        if not no_dump:
            log_dir = _get_log_path()
            path = f'{log_dir}/description.yml'
            print(f'{utils.INFO_COLOR}Project Log Storage: {log_dir}{utils.CLEAR_COLOR}')
            if not os.path.isfile(path):
                inspect['created'] = datetime.fromtimestamp(inspect['created'])
                with open(path, 'w') as f:
                    yaml.dump(inspect, f)

        # remove services
        for target in targets:
            if not no_dump:
                dump_logs(target[1], log_dir)
        if targets:
            res = API.service.remove(project_key, services=[target[1] for target in targets],
                                     stream=True)
            try:
                for _ in res:
                    if 'result' not in _:
                        sys.stdout.write(_['stream'])
                    if 'result' in _:
                        if _['result'] == 'stopped':
                            break
                        else:
                            print(_['stream'])
            except APIError as e:
                print(e)
                sys.exit(1)

        # Remove Network
        res = API.project.delete(project_key)
        try:
            for _ in res:
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'result' in _:
                    if _['result'] == 'succeed':
                        print('Network removed.')
                    break
        except APIError as e:
            print(e)
            sys.exit(1)
    print('Done.')


def down_force(no_dump):
    '''down project using local k8s for admin'''
    cli = k8s_ctlr.get_api_client(context=k8s_ctlr.get_current_context())
    project_key = utils.project_key(utils.get_workspace())
    workdir = utils.get_project(default_project)['workdir']
    network = k8s_ctlr.get_project_network(cli, project_key=project_key)

    if not network:
        print('Already stopped project.', file=sys.stderr)
        sys.exit(1)
    network_inspect = k8s_ctlr.inspect_project_network(network, cli)
    namespace = network_inspect['name']

    def _get_running_services():
        inspects = []
        _services = k8s_ctlr.get_services(project_key, cli=cli)
        for svc in _services.values():
            inspect = k8s_ctlr.inspect_service(svc, cli)
            inspects.append(inspect)
        return inspects

    def _get_log_path():
        timestamp = str(network_inspect['created'])
        time = str(datetime.fromtimestamp(int(timestamp))).replace(':', '-')
        log_dir = f'{workdir}/.logs/{time}'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        return log_dir

    def dump_logs(service, log_dir):
        path = f'{log_dir}/{service}.log'
        with open(path, 'w') as f:
            try:
                targets = k8s_ctlr.get_service_with_names_or_ids(
                    project_key, names_or_ids=[service], cli=cli)
            except exceptions.NotFound:
                print(f'Cannot get logs of pending service \'{service}\'')
            else:
                logs = k8s_ctlr.get_project_logs(
                    project_key, timestamps=True, targets=targets, cli=cli)
                for _ in logs:
                    log = _get_default_logs(_)
                    f.write(log)
                print(f'Service \'{service}\' log saved.')

    with interrupt_handler(message='Wait.', blocked=False):
        running_services = _get_running_services()
        targets = [(_['id'], _['name']) for _ in running_services]

        # Save desc & log
        if not no_dump:
            log_dir = _get_log_path()
            path = f'{log_dir}/description.yml'
            print(f'{utils.INFO_COLOR}Project Log Storage: '
                  f'{log_dir}{utils.CLEAR_COLOR}')
            if not os.path.isfile(path):
                network_inspect['created'] = \
                    datetime.fromtimestamp(network_inspect['created'])
                with open(path, 'w') as f:
                    yaml.dump(network_inspect, f)

        # remove services
        for target in targets:
            if not no_dump:
                dump_logs(target[1], log_dir)

        if targets:
            _services = [k8s_ctlr.get_service(target[1], namespace, cli)
                         for target in targets]
            res = k8s_ctlr.remove_services(_services, stream=True, cli=cli)
            try:
                for _ in res:
                    if 'result' not in _:
                        sys.stdout.write(_['stream'])
                    if 'result' in _:
                        if _['result'] == 'stopped':
                            break
                        else:
                            print(_['stream'])
            except APIError as e:
                print(e)
                sys.exit(1)

        # Remove Network
        res = k8s_ctlr.remove_project_network(network, stream=True, cli=cli)
        for _ in res:
            if 'stream' in _:
                sys.stdout.write(_['stream'])
            if 'result' in _:
                if _['result'] == 'succeed':
                    print('Network removed.')
                break
    print('Done.')


def logs(file: Optional[str], project_key: Optional[str],
         tail: bool, follow: bool, timestamps: bool, names_or_ids: List[str]):
    utils.process_file(file)
    if project_key is None:
        project_key = utils.project_key(utils.get_workspace())
    # Block not running.
    API.project.inspect(project_key)

    logs = API.project.log(project_key, tail, follow, timestamps, names_or_ids)

    colorkey = {}
    for _ in logs:
        if '[Ignored]' in _['stream']:
            continue
        _print_log(_, colorkey, 32, 20)


def scale(scales):
    scale_spec = dict([scale.split('=') for scale in scales])
    project_key = utils.project_key(utils.get_workspace())
    try:
        API.project.inspect(project_key)
    except NotFound:
        print('Cannot find running service.', file=sys.stderr)
        sys.exit(1)

    inspects = API.service.get(project_key)['inspects']
    services = [_['name'] for _ in inspects]

    for service in scale_spec:
        if service in services:
            API.service.scale(project_key, service, scale_spec[service])
            print(f'Service scale updated: {service}')
        else:
            print(f'Invalid service name: {service}')
