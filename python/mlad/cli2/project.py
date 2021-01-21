import sys
import os
import io
import time
import tarfile
from pathlib import Path
from datetime import datetime
from dateutil import parser
from mlad.core.docker import controller as ctlr
from mlad.core.default import project as default_project
from mlad.core import exception
from mlad.cli2.libs import utils
from mlad.cli2.libs import interrupt_handler
from mlad.cli2.Format import PROJECT
from mlad.cli2.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT

def _print_log(log, colorkey, max_name_width=32, len_short_id=10):
    name = log['name']
    namewidth = min(max_name_width, log['name_width'])
    if 'task_id' in log:
        name = f"{name}.{log['task_id'][:len_short_id]}"
        namewidth = min(max_name_width, namewidth + len_short_id + 1)
    msg = log['stream'].decode()
    timestamp = log['timestamp'].strftime("[%Y-%m-%d %H:%M:%S.%f]") if 'timestamp' in log else None
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

def list():
    cli = ctlr.get_docker_client()
    projects = {}
    for service in ctlr.get_services(cli).values():
        inspect = ctlr.inspect_service(service)
        default = { 
            'username': inspect['username'], 
            'project': inspect['name'], 
            'image': inspect['image'],
            'services': 0, 'replicas': 0, 'tasks': 0 
        }
        project_key = inspect['key']
        tasks = inspect['tasks'].values()
        tasks_state = [_['Status']['State'] for _ in tasks]
        projects[project_key] = projects[project_key] if project_key in projects else default
        projects[project_key]['services'] += 1
        projects[project_key]['replicas'] += inspect['replicas']
        projects[project_key]['tasks'] += tasks_state.count('running')
    columns = [('USERNAME', 'PROJECT', 'IMAGE', 'SERVICES', 'TASKS')]
    for project in projects:
        running_tasks = f"{projects[project]['tasks']}/{projects[project]['replicas']}"
        columns.append((projects[project]['username'], projects[project]['project'], projects[project]['image'], projects[project]['services'], f"{running_tasks:>5}"))
    utils.print_table(columns, 'Cannot find running project.', 64)

def status(all, no_trunc):
    cli = ctlr.get_docker_client()
    config = utils.read_config()

    project_key = utils.project_key(utils.get_workspace())
    # Block not running.
    network = ctlr.get_project_network(cli, project_key=project_key)
    if not network:
        print('Cannot find running service.', file=sys.stderr)
        sys.exit(1)
    inspect = ctlr.inspect_project_network(network)

    task_info = []
    for service_name, service in ctlr.get_services(cli, project_key).items():
        service_inspect = ctlr.inspect_service(service)
        try:
            for task_id, task in service_inspect['tasks'].items():
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
                    node = ctlr.get_nodes(cli, task['NodeID'])
                    node_inspect = ctlr.inspect_node(node)
                    task_info.append((
                        task_id,
                        service_name,
                        task['Slot'],
                        node_inspect['hostname'] if 'NodeID' in task else '-',
                        task['DesiredState'].title(), 
                        f"{task['Status']['State'].title()}", 
                        uptime,
                        ', '.join([_ for _ in service_inspect['ports']]),
                        task['Status']['Err'] if 'Err' in task['Status'] else '-'
                    ))
        except docker.errors.NotFound as e:
            pass
    columns = [('ID', 'SERVICE', 'SLOT', 'NODE', 'DESIRED STATE', 'CURRENT STATE', 'UPTIME', 'PORTS', 'ERROR')]
    columns_data = []
    for id, service, slot, node, desired_state, current_state, uptime, ports, error in task_info:
        columns_data.append((id, service, slot, node, desired_state, current_state, uptime, ports, error))
    columns_data = sorted(columns_data, key=lambda x: f"{x[1]}-{x[2]:08}")
    columns += columns_data

    print(f"USERNAME: [{config['account']['username']}] / PROJECT: [{inspect['project']}]")
    if no_trunc:
        utils.print_table(columns, 'Project is not running.', -1)
    else:
        utils.print_table(columns, 'Project is not running.')

def build(tagging, verbose):
    cli = ctlr.get_docker_client()
    config = utils.read_config()
    project_key = utils.project_key(utils.get_workspace())

    project = utils.get_project(default_project)
    
    # Generate Base Labels
    base_labels = ctlr.make_base_labels(utils.get_workspace(), config['account']['username'], project['project'])

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

    workspace = utils.getWorkingDir()
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
    with tarfile.open(fileobj=tarbytes, mode='w:') as tar:
        for name, arcname in utils.arcfiles(workspace, project['workspace']['ignore']):
            tar.add(name, arcname)
        tar.addfile(dockerfile_info, io.BytesIO(dockerfile.encode()))
    tarbytes.seek(0)

    # Build Image
    build_output = ctlr.build_image(cli, base_labels, tarbytes, dockerfile_info.name) 

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
        for _ in ctlr.push_images(cli, project_key):
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

    cli = ctlr.get_docker_client()
    base_labels = ctlr.make_base_labels(utils.get_workspace(), config['account']['username'], project['project'])
    project_key = base_labels['MLAD.PROJECT']
    
    with interrupt_handler(message='Wait.', blocked=True) as h:
        # Create Network
        try:
            for _ in ctlr.create_project_network(cli, base_labels, swarm=False):
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'result' in _:
                    if _['result'] == 'succeed':
                        network = _['output']
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
            for _ in ctlr.remove_project_network(cli, network):
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'status' in _:
                    if _['status'] == 'succeed':
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
    cli = ctlr.get_docker_client()

    base_labels = ctlr.make_base_labels(utils.get_workspace(), config['account']['username'], project['project'])
    project_key = base_labels['MLAD.PROJECT']
    
    # Get Network
    try:
        if not services:
            for _ in ctlr.create_project_network(cli, base_labels, swarm=True):
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'result' in _:
                    if _['result'] == 'succeed':
                        network = _['output']
                    break
        else:
            for _ in ctlr.create_project_network(cli, base_labels, swarm=True, allow_reuse=True):
                if 'stream' in _:
                    sys.stdout.write(_['stream'])
                if 'result' in _:
                    if _['result'] == 'succeed':
                        network = _['output']
                    break
    except exception.AlreadyExist as e:
        #print(e, file=sys.stderr)
        print('Already running project.', file=sys.stderr)
        sys.exit(1)


    # Check service status
    running_services = ctlr.get_services(cli, project_key)
    for service_name in targets:
        if service_name in running_services:
            print(f'Already running service[{service_name}] in project.', file=sys.stderr)
            del targets[service_name]

    with interrupt_handler(message='Wait.', blocked=True) as h:
        instances = ctlr.create_services(cli, network, targets)  
        for instance in instances:
            inspect = ctlr.inspect_service(instance)
            print(f"Starting {inspect['name']}...")
            time.sleep(1)
        if h.interrupted:
            pass
    print('Done.')

def down(services):
    cli = ctlr.get_docker_client()
    project_key = utils.project_key(utils.get_workspace())

    # Block duplicated running.
    network = ctlr.get_project_network(cli, project_key=project_key)
    if not network:
        print('Already stopped project.', file=sys.stderr)
        sys.exit(1)
    if services:
        running_services = ctlr.get_services(cli, project_key)
        for service_name in services:
            if not service_name in running_services:
                print(f'Already stopped service[{service_name}] in project.', file=sys.stderr)
                sys.exit(1)

    with interrupt_handler(message='Wait.', blocked=True):
        running_services = ctlr.get_services(cli, project_key).values()
        def filtering(_):
            inspect = ctlr.inspect_service(_)
            return not services or inspect['name'] in services
        targets = [_ for _ in running_services if filtering(_)]
        ctlr.remove_services(cli, targets)

        # Remove Network
        if not services:
            try:
                for _ in ctlr.remove_project_network(cli, network):
                    if 'stream' in _:
                        sys.stdout.write(_['stream'])
                    if 'status' in _:
                        if _['status'] == 'succeed':
                            print('Network removed.')
                        break
            except docker.errors.APIError as e:
                print('Network already removed.', file=sys.stderr)

    print('Done.')

def logs(tail, follow, timestamps, names_or_ids):
    cli = ctlr.get_docker_client()
    project_key = utils.project_key(utils.get_workspace())

    # Block not running.
    network = ctlr.get_project_network(cli, project_key=project_key)
    if not network:
        print('Cannot find running project.', file=sys.stderr)
        sys.exit(1)

    colorkey = {}
    for _ in ctlr.get_project_logs(cli, project_key, tail, follow, timestamps, names_or_ids):
        _print_log(_, colorkey, 32, ctlr.SHORT_LEN)

def scale(scales):
    scale_spec = dict([ scale.split('=') for scale in scales ])

    cli = ctlr.get_docker_client()
    project_key = utils.project_key(utils.get_workspace())
    
    # Block not running.
    network = ctlr.get_project_network(cli, project_key=project_key)
    if not network:
        print('Cannot find running project.', file=sys.stderr)
        sys.exit(1)

    # Inspect Data
    inspect = ctlr.inspect_project_network(network)

    services = ctlr.get_services(cli, project_key)
    for name, service in [(_, services[_]) for _ in services if _ in scale_spec]:
        try:
            if service.scale(int(scale_spec[name])):
                print(f'Change scale service [{name}].')
            else:
                print(f'Failed to change scale service [{name}].')
        except docker.errors.NotFound:
            print(f'Cannot find service [{name}].', file=sys.stderr)



