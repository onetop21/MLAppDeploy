import sys
import os
import io
import time
import tarfile
import json
import base64
import docker
from pathlib import Path
from datetime import datetime
from dateutil import parser
from functools import lru_cache
from requests.exceptions import HTTPError
from mlad.core.docker import controller as ctlr
from mlad.core.default import config as default_config
from mlad.core.default import project as default_project
from mlad.core.default import plugin as default_plugin
from mlad.core import exception
from mlad.core.libs import utils as core_utils
from mlad.cli.libs import utils
from mlad.cli.libs import datastore as ds
from mlad.cli.libs import interrupt_handler
from mlad.cli.Format import PLUGIN
from mlad.cli.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT
from mlad.api import API
from mlad.api.exception import APIError, NotFoundError

@lru_cache(maxsize=None)
def get_username(config):
    with API(config.mlad.address, config.mlad.token.user) as api:
        res = api.auth.token_verify()
    if res['result']:
        return res['data']['username']
    else:
        raise RuntimeError("Token is not valid.")

def _print_log(log, colorkey, max_name_width=32, len_short_id=10):
    name = log['name']
    namewidth = min(max_name_width, log['name_width'])
    if 'task_id' in log:
        name = f"{name}.{log['task_id'][:len_short_id]}"
        namewidth = min(max_name_width, namewidth + len_short_id + 1)
    msg = log['stream'] if isinstance(log['stream'], str) else log['stream'].decode()
    timestamp = f'[{log["timestamp"]}]' if 'timestamp' in log else None
    #timestamp = log['timestamp'].strftime("[%Y-%m-%d %H:%M:%S.%f]") if 'timestamp' in log else None
    if msg.startswith('Error'):
        sys.stderr.write(f'{utils.ERROR_COLOR}{msg}{utils.CLEAR_COLOR}')
    else:
        colorkey[name] = colorkey[name] if name in colorkey else utils.color_table()[utils.color_index()]
        if timestamp:
            sys.stdout.write(("{}{:%d}{} {} {}" % namewidth).format(colorkey[name], name, utils.CLEAR_COLOR, timestamp, msg))
        else:
            sys.stdout.write(("{}{:%d}{} {}" % namewidth).format(colorkey[name], name, utils.CLEAR_COLOR, msg))

# Main CLI Functions
def init(name, version, maintainer):
    if utils.read_project():
        print('Already generated plugin manifest file.', file=sys.stderr)
        sys.exit(1)

    if not name: name = input('Plugin Name : ')

    with open(utils.DEFAULT_PLUGIN_FILE, 'w') as f:
        f.write(PLUGIN.format(
            NAME=name,
            VERSION=version,
            MAINTAINER=maintainer,
        ))

def installed(no_trunc):
    config = utils.read_config()
    projects = {}
    api = API(config.mlad.address, config.mlad.token.user)
    networks = api.project.get(['MLAD.PROJECT.TYPE=plugin'])
    columns = [('USERNAME', 'PLUGIN', 'VERSION', 'URL', 'STATUS', 'TASKS', 'AGE')]
    for network in networks:
        project_key = network['key']
        default = { 
            'username': network['username'], 
            'project': network['project'], 
            'image': network['image'],
            'version': network['version'],
            'url': '',
            'age': '',
            'status': 'running',
            'replicas': 0, 'services': 0, 'tasks': 0,
            
        }
        projects[project_key] = projects[project_key] if project_key in projects else default
        res = api.service.get(project_key=project_key)
        for inspect in res['inspects']:
            if no_trunc:
                base_url = f"http://{config['mlad']['host']}"
                if not config['mlad']['port'] in [80, 8440] : base_url += f":{config['mlad']['port']}"
            else:
                base_url = ''
            projects[project_key]['url'] = f"{base_url}{inspect.get('ingress')}" or '-'
            uptime = (datetime.utcnow() - parser.parse(inspect['created']).replace(tzinfo=None)).total_seconds()
            if uptime > 24 * 60 * 60:
                uptime = f"{uptime // (24 * 60 * 60):.0f} days"
            elif uptime > 60 * 60:
                uptime = f"{uptime // (60 * 60):.0f} hours"
            elif uptime > 60:
                uptime = f"{uptime // 60:.0f} minutes"
            else:
                uptime = f"{uptime:.0f} seconds"
            projects[project_key]['age'] = uptime
            tasks = inspect['tasks'].values()
            tasks_state = [_['status']['state'] for _ in tasks]
            projects[project_key]['services'] += 1
            projects[project_key]['replicas'] += inspect['replicas']
            projects[project_key]['tasks'] += tasks_state.count('Running')
    for project in projects:
        if projects[project]['services'] > 0:
            running_tasks = f"{projects[project]['tasks']}/{projects[project]['replicas']}"
            columns.append((projects[project]['username'], projects[project]['project'], projects[project]['version'], projects[project]['url'], projects[project]['status'].title(), f"{running_tasks}", projects[project]['age']))
        else:
            columns.append((projects[project]['username'], projects[project]['project'], '-', '-', '-', '-', '-'))
    utils.print_table(*([columns, 'Cannot find running plugin.'] + ([0] if no_trunc else [])))

#def instance(with_build):
#    project = utils.get_project(default_project)
#
#    if with_build: build(False, True)
#
#    print('Deploying test container image to local...')
#    config = utils.read_config()
#
#    cli = ctlr.get_api_client()
#    base_labels = core_utils.base_labels(utils.get_workspace(), get_username(config), project['project'], config['docker']['registry'])
#    project_key = base_labels['MLAD.PROJECT']
#    
#    with interrupt_handler(message='Wait.', blocked=True) as h:
#        try:
#            extra_envs = utils.get_service_env(config)
#            for _ in ctlr.create_project_network(cli, base_labels, extra_envs, swarm=False, stream=True):
#                if 'stream' in _:
#                    sys.stdout.write(_['stream'])
#                if 'result' in _:
#                    if _['result'] == 'succeed':
#                        network = ctlr.get_project_network(cli, network_id=_['id'])
#                    else:
#                        print(f"Unknown Stream Result [{_['stream']}]")
#                    break
#        except exception.AlreadyExist as e:
#            print('Already running project.', file=sys.stderr)
#            sys.exit(1)
#
#        # Start Containers
#        instances = ctlr.create_containers(cli, network, project['services'] or {})  
#        for instance in instances:
#            inspect = ctlr.inspect_container(instance)
#            print(f"Starting {inspect['name']}...")
#            time.sleep(1)
#
#    # Show Logs
#    with interrupt_handler(blocked=False) as h:
#        colorkey = {}
#        for _ in ctlr.container_logs(cli, project_key, 'all', True, False):
#            _print_log(_, colorkey, 32, ctlr.SHORT_LEN)
#
#    # Stop Containers and Network
#    with interrupt_handler(message='Wait.', blocked=True):
#        containers = ctlr.get_containers(cli, project_key).values()
#        ctlr.remove_containers(cli, containers)
#
#        try:
#            for _ in ctlr.remove_project_network(cli, network, stream=True):
#                if 'stream' in _:
#                    sys.stdout.write(_['stream'])
#                if 'result' in _:
#                    if _['result'] == 'succeed':
#                        print('Network removed.')
#                    break
#        except docker.errors.APIError as e:
#            print('Network already removed.', file=sys.stderr)
#    print('Done.')

def install(name_version, arguments):
    config = utils.read_config()
    cli = ctlr.get_api_client()
    name, version = name_version.split(':') if ':' in name_version else (name_version, 'latest')
    username = get_username(config)
    basename = f'{username}-{name.lower()}-plugin'
    reponame = f"{basename}:{version}"
    project_key = core_utils.project_key(basename)
    if version != 'latest':
        images = ctlr.get_images(cli, project_key=project_key, extra_labels=[f"MLAD.PROJECT.IMAGE={reponame}"])
    else:
        images = ctlr.get_images(cli, project_key=project_key)
        tag_key = lambda x: chr(0xFFFF) if x[0].endswith('latest') else x[0].rsplit(':', 1)[-1]
        images = sorted([(_, i) for i in images for _ in i.tags], key=tag_key)
        images = [images[-1][1]]

    # select suitable image
    if not images:
        print(f'Not installed plugin [{name_version}].', file=sys.stderr)
        return
    image = images[0]
    inspect = ctlr.inspect_image(image)

    # set prefix to image name
    parsed_url = utils.parse_url(config.docker.registry.address)
    registry = parsed_url['address']
    if config.docker.registry.namespace:
        registry = f"{registry}/{config.docker.registry.namespace}"
    repository = f"{registry}/{basename}"
    image.tag(repository, tag=inspect['tag'])
    full_repository = f"{repository}:{inspect['tag']}"

    # Upload Image
    print('Update plugin image to registry...')
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
    # Get Base Labels
    base_labels = image.labels
    base_labels['MLAD.PROJECT.IMAGE']=full_repository
    target = json.loads(base64.urlsafe_b64decode(base_labels.get('MLAD.PROJECT.PLUGIN_MANIFEST').encode()).decode())
    target['name'] = name
    target['service_type'] = 'plugin'
    if arguments:
        target['arguments'] = f"{' '.join(arguments)}"
    target['deploy']['restart_policy']['condition'] = 'always'

    # AuthConfig
    headers = {'auths': json.loads(base64.urlsafe_b64decode(ctlr.get_auth_headers(cli)['X-Registry-Config'] or b'e30K'))}
    encoded = base64.urlsafe_b64encode(json.dumps(headers).encode())
    credential = encoded.decode()
   
    api = API(config.mlad.address, config.mlad.token.user)
    extra_envs = ds.get_env(default_config['client'](config)) + \
            ["MLAD_USER_TOKEN={config.mlad.token.user}"]

    res = api.project.create({'name': inspect['project_name'], 'version': inspect['version'], 'maintainer': inspect['maintainer']},
            base_labels, extra_envs, credential=credential, swarm=True, allow_reuse=False)
    try:
        for _ in res:
            if 'stream' in _:
                sys.stdout.write(_['stream'])
            if 'result' in _:
                if _['result'] == 'succeed':
                    network_id = _['id']
                    break 
    except APIError as e:
        print(e)
        sys.exit(1)

    # Check service status
    if name in [_['name'] for _ in api.service.get(project_key)['inspects']]:
        print(f'Already running plugin[{service_name}] in cluster.', file=sys.stderr)
        return 

    with interrupt_handler(message='Wait.', blocked=True) as h:
        try:
            instances = api.service.create(project_key, [target])
            for instance in instances:
                inspect = api.service.inspect(project_key, instance)
                print(f"Starting {inspect['name']}...")
                time.sleep(1)
        except APIError as e:
            print(e)
        if h.interrupted:
            pass

    print('Done.')

def uninstall(name):
    config = utils.read_config()
    api = API(config.mlad.address, config.mlad.token.user)

    basename = f'{get_username(config)}-{name.lower()}-plugin'
    project_key = core_utils.project_key(basename)

    # Block duplicated running.
    try:
        inspect = api.project.inspect(project_key=project_key)
    except NotFoundError as e:
        print(f'Already stopped plugin[{name}].', file=sys.stderr)
        return

    with interrupt_handler(message='Wait.', blocked=False):
        res = api.project.delete(project_key)
        try:
            for _ in res:
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'status' in _:
                    if _['status'] == 'succeed':
                        print('Network removed.')
                    break
        except APIError as e:
            print(e)
            sys.exit(1)
    print('Done.')

def logs(tail, follow, timestamps, names_or_ids):
    config = utils.read_config()
    project_key = utils.project_key(utils.get_workspace())
    api = API(config.mlad.address, config.mlad.token.user)
    # Block not running.
    try:
        project = api.project.inspect(project_key)
        logs = api.project.log(project_key, tail, follow,
            timestamps, names_or_ids)
    except NotFoundError as e:
        print('Cannot find running service.', file=sys.stderr)
        sys.exit(1)

    colorkey = {}
    try:
        for _ in logs:
            _print_log(_, colorkey, 32, 20)
    except APIError as e:
        print(e)
        sys.exit(1)

