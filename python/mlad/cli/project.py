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
from mlad.core import exception
from mlad.cli.libs import utils
from mlad.cli.libs import interrupt_handler
from mlad.cli.Format import PROJECT
from mlad.cli.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT
from mlad.api import API
from mlad.api.exception import APIError, NotFoundError

@lru_cache(maxsize=None)
def get_username(config):
    with API(utils.to_url(config.mlad), config.mlad.token.user) as api:
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
def init(name, version, author):
    if utils.read_project():
        print('Already generated project file.', file=sys.stderr)
        sys.exit(1)

    if not name: name = input('Project Name : ')
    #if not version: version = input('Project Version : ')
    #if not author: author = input('Project Author : ')

    with open(utils.PROJECT_FILE, 'w') as f:
        f.write(PROJECT.format(
            NAME=name,
            VERSION=version,
            AUTHOR=author,
        ))

def list(no_trunc):
    config = utils.read_config()
    projects = {}
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    networks = api.project.get()
    for network in networks:
        project_key = network['key']
        default = { 
            'username': network['username'], 
            'project': network['project'], 
            'image': network['image'],
            'services': 0, 'replicas': 0, 'tasks': 0,
            'hostname': network['workspace']['hostname'],
            'workspace': network['workspace']['path'],
        }
        projects[project_key] = projects[project_key] if project_key in projects else default
        res = api.service.get(project_key=project_key)
        if res['mode'] == 'swarm':
            for inspect in res['inspects']:
                tasks = inspect['tasks'].values()
                tasks_state = [_['Status']['State'] for _ in tasks]
                projects[project_key]['services'] += 1
                projects[project_key]['replicas'] += inspect['replicas']
                projects[project_key]['tasks'] += tasks_state.count('running')
        else:
            for inspect in res['inspects']:
                tasks = inspect['tasks'].values()
                tasks_state = [_['status']['state'] for _ in tasks]
                projects[project_key]['services'] += 1
                projects[project_key]['replicas'] += inspect['replicas']
                projects[project_key]['tasks'] += tasks_state.count('Running')
        columns = [('USERNAME', 'PROJECT', 'IMAGE', 'SERVICES', 'TASKS', 'HOSTNAME', 'WORKSPACE')]
        for project in projects:
            if projects[project]['services'] > 0:
                running_tasks = f"{projects[project]['tasks']}/{projects[project]['replicas']}"
                columns.append((projects[project]['username'], projects[project]['project'], projects[project]['image'], projects[project]['services'], f"{running_tasks:>5}", projects[project]['hostname'], projects[project]['workspace']))
            else:
                columns.append((projects[project]['username'], projects[project]['project'], projects[project]['image'], '-', '-', projects[project]['hostname'], projects[project]['workspace']))
    utils.print_table(*([columns, 'Cannot find running project.'] + ([0] if no_trunc else [])))

def status(all, no_trunc):
    config = utils.read_config()
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    project_key = utils.project_key(utils.get_workspace())
    # Block not running.
    try:
        inspect = api.project.inspect(project_key=project_key)
    except NotFoundError as e:
        print('Cannot find running project.', file=sys.stderr)
        sys.exit(1)

    task_info = []
    res = api.service.get(project_key)
    if res['mode'] == 'swarm':
        for inspect in res['inspects']:
            try:
                for task_id, task in api.service.get_tasks(project_key, inspect['id']).items():
                    uptime = (datetime.utcnow() - parser.parse(task['Status']['Timestamp']).replace(tzinfo=None)).total_seconds()
                    if uptime > 24 * 60 * 60:
                        uptime = f"{uptime // (24 * 60 * 60):.0f} days"
                    elif uptime > 60 * 60:
                        uptime = f"{uptime // (60 * 60):.0f} hours"
                    elif uptime > 60:
                        uptime = f"{uptime // 60:.0f} minutes"
                    else:
                        uptime = f"{uptime:.0f} seconds"
                    if all or task['Status']['State'] not in ['shutdown', 'failed']:
                        if 'NodeID' in task:
                            node_inspect = api.node.inspect(task['NodeID'])
                        task_info.append((
                            task_id,
                            inspect['name'],
                            task['Slot'],
                            node_inspect['hostname'] if 'NodeID' in task else '-',
                            task['DesiredState'].title(), 
                            f"{task['Status']['State'].title()}", 
                            uptime,
                            ', '.join([_ for _ in inspect['ports']]),
                            task['Status']['Err'] if 'Err' in task['Status'] else '-'
                        ))
            except NotFoundError as e:
                pass
        
        columns = [('ID', 'SERVICE', 'SLOT', 'NODE', 'DESIRED STATE', 'CURRENT STATE', 'UPTIME', 'PORTS', 'ERROR')]
        columns_data = []
        for id, service, slot, node, desired_state, current_state, uptime, ports, error in task_info:
            columns_data.append((id, service, slot, node, desired_state, current_state, uptime, ports, error))
        columns_data = sorted(columns_data, key=lambda x: f"{x[1]}-{x[2]:08}")
        columns += columns_data
    else:
        for inspect in res['inspects']:
            try:
                for pod_name, pod in api.service.get_tasks(project_key, inspect['id']).items():
                    ready_cnt = 0
                    restart_cnt = 0
                    container_cnt = len(pod['container_status'])
                    for _ in pod['container_status']:
                        restart_cnt += _['restart']
                        if _['ready']==True:
                            ready_cnt+=1
                    ready = f'{ready_cnt}/{container_cnt}'
            
                    uptime = (datetime.utcnow() - parser.parse(pod['created']).replace(tzinfo=None)).total_seconds()
                    if uptime > 24 * 60 * 60:
                        uptime = f"{uptime // (24 * 60 * 60):.0f} days"
                    elif uptime > 60 * 60:
                        uptime = f"{uptime // (60 * 60):.0f} hours"
                    elif uptime > 60:
                        uptime = f"{uptime // 60:.0f} minutes"
                    else:
                        uptime = f"{uptime:.0f} seconds"
                    #if all or task['Status']['State'] not in ['shutdown', 'failed']:
                    task_info.append((
                        pod_name,
                        inspect['name'],
                        #ready,
                        pod['node'],
                        pod['phase'],
                        'Running' if pod['status']['state'] == 'Running' else pod['status']['detail']['reason'],
                        restart_cnt,
                        uptime
                    ))
            except NotFoundError as e:
                pass
        columns = [('NAME', 'SERVICE', 'NODE','PHASE', 'STATUS','RESTART', 'AGE')]
        columns_data = []
        for name, service, node, phase, status, restart_cnt, uptime in task_info:
            columns_data.append((name, service, node, phase, status, restart_cnt, uptime))
        columns_data = sorted(columns_data, key=lambda x: x[1])
        columns += columns_data     
    print(f"USERNAME: [{get_username(config)}] / PROJECT: [{inspect['project']}]")
    utils.print_table(*([columns, 'Cannot find running services.'] + ([0] if no_trunc else [])))

def build(tagging, verbose, no_cache):
    config = utils.read_config()
    cli = ctlr.get_api_client()
    project_key = utils.project_key(utils.get_workspace())

    project = utils.get_project(default_project)
    
    # Generate Base Labels
    base_labels = ctlr.make_base_labels(utils.get_workspace(), get_username(config), project['project'], config['docker']['registry'])

    # Prepare Latest Image
    latest_image = None
    commit_number = 1
    images = ctlr.get_images(cli, project_key)
    if len(images):
        latest_image = sorted(filter(None, [ image if tag.endswith('latest') else None for image in images for tag in image.tags ]), key=lambda x: str(x))
        if latest_image and len(latest_image): latest_image = latest_image[0]
        tags = sorted(filter(None, [ tag if not tag.endswith('latest') else None for image in images for tag in image.tags ]))
        if len(tags): commit_number=int(tags[-1].split('.')[-1])+1
    image_version = f"{base_labels['MLAD.PROJECT.VERSION']}.{commit_number}"

    print('Generating project image...')

    # Prepare workspace data from project file
    envs = []
    for key in project['workspace']['env'].keys():
        envs.append(DOCKERFILE_ENV.format(
            KEY=key,
            VALUE=project['workspace']['env'][key]
        ))
    requires = []
    for key in project['workspace']['requires'].keys():
        if key == 'apt':
            requires.append(DOCKERFILE_REQ_APT.format(
                SRC=project['workspace']['requires'][key]
            ))
        elif key == 'pip':
            requires.append(DOCKERFILE_REQ_PIP.format(
                SRC=project['workspace']['requires'][key]
            )) 

    # Dockerfile to memory
    dockerfile = DOCKERFILE.format(
        BASE=project['workspace']['base'],
        AUTHOR=project['project']['author'],
        ENVS='\n'.join(envs),
        PRESCRIPTS=';'.join(project['workspace']['prescripts']) if len(project['workspace']['prescripts']) else "echo .",
        REQUIRES='\n'.join(requires),
        POSTSCRIPTS=';'.join(project['workspace']['postscripts']) if len(project['workspace']['postscripts']) else "echo .",
        COMMAND='[{}]'.format(', '.join(
            [f'"{item}"' for item in project['workspace']['command'].split()] + 
            [f'"{item}"' for item in project['workspace']['arguments'].split()]
        )),
    )

    tarbytes = io.BytesIO()
    dockerfile_info = tarfile.TarInfo('.dockerfile')
    dockerfile_info.size = len(dockerfile)
    with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
        for name, arcname in utils.arcfiles(project['project']['workdir'], project['workspace']['ignore']):
            tar.add(name, arcname)
        tar.addfile(dockerfile_info, io.BytesIO(dockerfile.encode()))
    tarbytes.seek(0)

    # Build Image
    build_output = ctlr.build_image(cli, base_labels, tarbytes, dockerfile_info.name, no_cache, stream=True) 

    # Print build output
    for _ in build_output:
        if 'error' in _:
            sys.stderr.write(f"{_['error']}\n")
            sys.exit(1)
        elif 'stream' in _:
            if verbose:
                sys.stdout.write(_['stream'])

    image = ctlr.get_image(cli, base_labels['MLAD.PROJECT.IMAGE'])
    # Check duplicated.
    tagged = False
    if latest_image != image:
        if tagging:
            image.tag(repository, tag=image_version)
            tagged = True
        if latest_image and len(latest_image.tags) < 2 and latest_image.tags[-1].endswith(':latest'):
            latest_image.tag('remove')
            cli.images.remove('remove')
    else:
        if tagging and len(latest_image.tags) < 2:
            image.tag(repository, tag=image_version)
            tagged = True
        else:
            print('Already built project to image.', file=sys.stderr)

    if tagged:
        print(f"Built Image: {'/'.join(repository.split('/')[1:])}:{image_version}")

    # Upload Image
    print('Update project image to registry...')
    try:
        for _ in ctlr.push_images(cli, project_key, stream=True):
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

    print('Done.')

def test(with_build):
    project = utils.get_project(default_project)

    if with_build: build(False, True)

    print('Deploying test container image to local...')
    config = utils.read_config()

    cli = ctlr.get_api_client()
    base_labels = ctlr.make_base_labels(utils.get_workspace(), get_username(config), project['project'], config['docker']['registry'])
    project_key = base_labels['MLAD.PROJECT']
    
    with interrupt_handler(message='Wait.', blocked=True) as h:
        try:
            extra_envs = utils.get_service_env(config)
            for _ in ctlr.create_project_network(cli, base_labels, extra_envs, swarm=False, stream=True):
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'result' in _:
                    if _['result'] == 'succeed':
                        network = ctlr.get_project_network(cli, network_id=_['id'])
                    else:
                        print(f"Unknown Stream Result [{_['stream']}]")
                    break
        except exception.AlreadyExist as e:
            print('Already running project.', file=sys.stderr)
            sys.exit(1)

        # Start Containers
        instances = ctlr.create_containers(cli, network, project['services'] or {})  
        for instance in instances:
            inspect = ctlr.inspect_container(instance)
            print(f"Starting {inspect['name']}...")
            time.sleep(1)

    # Show Logs
    with interrupt_handler(blocked=False) as h:
        colorkey = {}
        for _ in ctlr.container_logs(cli, project_key, 'all', True, False):
            _print_log(_, colorkey, 32, ctlr.SHORT_LEN)

    # Stop Containers and Network
    with interrupt_handler(message='Wait.', blocked=True):
        containers = ctlr.get_containers(cli, project_key).values()
        ctlr.remove_containers(cli, containers)

        try:
            for _ in ctlr.remove_project_network(cli, network, stream=True):
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'result' in _:
                    if _['result'] == 'succeed':
                        print('Network removed.')
                    break
        except docker.errors.APIError as e:
            print('Network already removed.', file=sys.stderr)
    print('Done.')

def up(services):
    project = utils.get_project(default_project)

    print('Deploying services to cluster...')
    if services:
        targets = {}
        for name in services:
            if name in project['services']:
                targets[name] = project['services'][name]
            else:
                print(f'Cannot find service[{name}] in mlad-project.yaml.', file=sys.stderr)
                sys.exit(1)
    else:
        targets = project['services'] or {}
            
    config = utils.read_config()
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    base_labels = ctlr.make_base_labels(utils.get_workspace(), get_username(config), project['project'], config['docker']['registry'])
    project_key = base_labels['MLAD.PROJECT']

    # AuthConfig
    cli = ctlr.get_api_client()
    headers = {'auths': json.loads(base64.urlsafe_b64decode(ctlr.get_auth_headers(cli)['X-Registry-Config']))}
    encoded = base64.urlsafe_b64encode(json.dumps(headers).encode())
    credential = encoded.decode()
   
    extra_envs = utils.get_service_env(default_config['client'](config))
    if not services:
        res = api.project.create(project['project'], base_labels,
            extra_envs, credential=credential, swarm=True, allow_reuse=False)
    else:
        res = api.project.create(project['project'], base_labels,
            extra_envs, credential=credential, swarm=True, allow_reuse=True)
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
    running_services = api.service.get(project_key)['inspects']
    excludes = []
    for service_name in targets:
        running_svc_names = [_['name'] for _ in running_services]
        if service_name in running_svc_names:
            print(f'Already running service[{service_name}] in project.', file=sys.stderr)
            excludes.append(service_name)
    for _ in excludes: del targets[_]

    def _target_model(targets):
        services = []
        for k, v in targets.items():
            v['name']=k
            services.append(v)
        return services

    with interrupt_handler(message='Wait.', blocked=True) as h:
        target_model = _target_model(targets)
        try:
            instances = api.service.create(project_key, target_model)
            for instance in instances:
                inspect = api.service.inspect(project_key, instance)
                print(f"Starting {inspect['name']}...")
                time.sleep(1)
        except APIError as e:
            print(e)
        if h.interrupted:
            pass

    print('Done.')

def down(services):
    config = utils.read_config()
    project_key = utils.project_key(utils.get_workspace())

    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    # Block duplicated running.
    try:
        inspect = api.project.inspect(project_key=project_key)
    except NotFoundError as e:
        print('Already stopped project.', file=sys.stderr)
        sys.exit(1)

    if services:
        running_services = api.service.get(project_key)['inspects']
        running_svc_names = [ _['name'] for _ in running_services ]
        for service_name in services:
            if not service_name in running_svc_names:
                print(f'Already stopped service[{service_name}] in project.', file=sys.stderr)
                sys.exit(1)
    
    with interrupt_handler(message='Wait.', blocked=False):
        running_services = api.service.get(project_key)['inspects']
      
        def filtering(inspect):
            return not services or inspect['name'] in services
        targets = [ _['id'] for _ in running_services if filtering(_) ]
        for target in targets:
            res = api.service.remove(project_key, target)
            print(res['message'])

        #Remove Network
        if not services:
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
    print(utils.get_workspace())
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
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


def scale(scales):
    scale_spec = dict([ scale.split('=') for scale in scales ])
    config = utils.read_config()
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    project_key = utils.project_key(utils.get_workspace())
    try:    
        project = api.project.inspect(project_key)
    except NotFoundError as e:
        print('Cannot find running service.', file=sys.stderr)
        sys.exit(1)

    inspects = api.service.get(project_key)['inspects']

    services = dict([(_['name'], _['id']) for _ in inspects])
    for service in scale_spec:
        if service in services:
            res = api.service.scale(project_key, services[service],
                scale_spec[service])
            print(f'Service scale updated: {service}')
        else:
            print(f'Invalid service name: {service}')

    
    

