import sys

from typing import Optional, List

from mlad.cli.libs import utils
from mlad.cli.format import PROJECT
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
    project_specs = API.project.get()

    columns = [('USERNAME', 'PROJECT', 'KIND', 'KEY', 'APPS',
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

        used = {'cpu': 0, 'gpu': 0, 'mem': 0}
        resources = API.project.resource(project_key)
        for _, resource in resources.items():
            used['mem'] += resource['mem'] if resource['mem'] is not None else 0
            used['cpu'] += resource['cpu'] if resource['cpu'] is not None else 0
            used['gpu'] += resource['gpu']
        for k in used:
            used[k] = used[k] if no_trunc else round(used[k], 1)

        projects[project_key].update(used)

    for project in projects.values():
        if project['apps'] > 0:
            running_tasks = f"{project['tasks']}/{project['replicas']}"
            columns.append((project['username'], project['project'],
                            project['kind'], project['key'],
                            project['apps'], f"{running_tasks:>5}", project['hostname'],
                            project['workspace'], project['age'],
                            project['mem'], project['cpu'], project['gpu']))
        else:
            columns.append((project['username'], project['project'],
                            project['kind'], project['key'],
                            '-', '-', project['hostname'],
                            project['workspace'], project['age'],
                            project['mem'], project['cpu'], project['gpu']))
    utils.print_table(columns, 'Cannot find running projects.', 0 if no_trunc else 32, False)


def status(file: Optional[str], project_key: Optional[str], all: bool, no_trunc: bool, event: bool):
    utils.process_file(file)
    config = config_core.get()
    if project_key is None:
        project_key = utils.workspace_key()
    # Block not running.
    try:
        API.project.inspect(project_key=project_key)
        resources = API.project.resource(project_key)
    except NotFound:
        print('Cannot find running project.', file=sys.stderr)
        sys.exit(1)

    events = []
    columns = [
        ('NAME', 'APP', 'NODE', 'PHASE', 'STATUS', 'RESTART', 'AGE', 'PORTS', 'MEM(Mi)', 'CPU', 'GPU')]
    for spec in API.app.get(project_key)['specs']:
        task_info = []
        try:
            ports = ','.join(map(str, spec['ports']))
            for pod_name, pod in API.app.get_tasks(project_key, spec['name']).items():
                ready_cnt = 0
                restart_cnt = 0
                if pod['container_status']:
                    for _ in pod['container_status']:
                        restart_cnt += _['restart']
                        if _['ready']:
                            ready_cnt += 1

                age = utils.created_to_age(pod['created'])

                res = resources[spec['name']].copy()
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
                        spec['name'],
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
    print(f"USERNAME: [{username}] / PROJECT: [{spec['project']}]")
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
    # Block not running.
    API.project.inspect(project_key)

    logs = API.project.log(project_key, tail, follow, timestamps, names_or_ids)

    colorkey = {}
    for log in logs:
        if '[Ignored]' in log['stream']:
            continue
        _print_log(log, colorkey, 32, 20)


def ingress():
    config = config_core.get()
    address = config['apiserver']['address'].rsplit('/beta')[0]
    specs = API.app.get()['specs']
    rows = [('USERNAME', 'PROJECT NAME', 'APP NAME', 'KEY', 'PATH')]
    for spec in specs:
        if spec['ingress'] != '':
            username = spec['username']
            project_name = spec['project']
            app_name = spec['name']
            key = spec['key']
            path = f'{address}{spec["ingress"]}'
            rows.append((username, project_name, app_name, key, path))
    utils.print_table(rows, 'Cannot find running deployments', 0, False)