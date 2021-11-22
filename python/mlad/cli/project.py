import sys

from typing import Optional, List
from datetime import datetime
from dateutil import parser


from mlad.cli.libs import utils
from mlad.cli.Format import PROJECT
from mlad.cli import config as config_core
from mlad.api import API
from mlad.api.exceptions import NotFound


def _parse_log(log, max_name_width=32, len_short_id=10):
    name = log['name']
    namewidth = min(max_name_width, log['name_width'])if 'name_width' in log else max_name_width
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
        if not msg.endswith('\n'):
            msg+='\n'
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


def status(file: Optional[str], project_key: Optional[str], all: bool, no_trunc: bool, event: bool):
    utils.process_file(file)
    config = config_core.get()
    if project_key is None:
        project_key = utils.workspace_key()
    # Block not running.
    try:
        inspect = API.project.inspect(project_key=project_key)
        resources = API.project.resource(project_key)
    except NotFound:
        print('Cannot find running project.', file=sys.stderr)
        sys.exit(1)

    res = API.service.get(project_key)
    events = []
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

                if event and len(pod['events']) > 0:
                    events += pod['events']
        except NotFound:
            pass
        columns += sorted([tuple(elem) for elem in task_info], key=lambda x: x[1])
    username = utils.get_username(config.session)
    print(f"USERNAME: [{username}] / PROJECT: [{inspect['project']}]")
    utils.print_table(columns, 'Cannot find running services.', 0 if no_trunc else 32, False)

    if event:
        sorted_events = sorted(events, key=lambda e: e['datetime'])
        colorkey = {}
        print('\nEVENTS:')
        for _ in sorted_events:
            _['timestamp'] = _.pop('datetime')
            _['stream'] = _.pop('message')
            _print_log(_, colorkey, 32, 20)


def logs(file: Optional[str], project_key: Optional[str],
         tail: bool, follow: bool, timestamps: bool, names_or_ids: List[str]):
    utils.process_file(file)
    if project_key is None:
        project_key = utils.workspace_key()
    # Block not running.
    API.project.inspect(project_key)

    logs = API.project.log(project_key, tail, follow, timestamps, names_or_ids)

    colorkey = {}
    for _ in logs:
        if '[Ignored]' in _['stream']:
            continue
        _print_log(_, colorkey, 32, 20)
