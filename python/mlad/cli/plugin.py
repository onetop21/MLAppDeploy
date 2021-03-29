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
from mlad.cli.libs import interrupt_handler
from mlad.cli.Format import PLUGIN
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

def install(verbose, no_cache):
    config = utils.read_config()
    cli = ctlr.get_api_client()
    
    plugin = utils.get_manifest('plugin', default_plugin)
    
    # Generate Base Labels
    base_labels = core_utils.base_labels(
        utils.get_workspace(), 
        get_username(config), 
        plugin['plugin'], 
        config['docker']['registry'], 
        'plugin'
    )
    plugin_key = base_labels['MLAD.PROJECT']

    # Append service manfest using label.
    base_labels['MLAD.PROJECT.PLUGIN_MANIFEST']=base64.urlsafe_b64encode(json.dumps(plugin['service']).encode()).decode()

    # Prepare Latest Image
    latest_image = None
    images = ctlr.get_images(cli, extra_labels=['MLAD.PROJECT.TYPE=plugin'])
    if len(images):
        latest_image = sorted(filter(None, [ image if tag.endswith('latest') else None for image in images for tag in image.tags ]), key=lambda x: str(x))
        if latest_image and len(latest_image): latest_image = latest_image[0]
    image_version = f"{base_labels['MLAD.PROJECT.VERSION']}"

    print('Generating plugin image...')

    if plugin['workspace'] != default_plugin({})['workspace']:
        # Prepare workspace data from plugin manifest file
        envs = []
        for key in plugin['workspace']['env'].keys():
            envs.append(DOCKERFILE_ENV.format(
                KEY=key,
                VALUE=plugin['workspace']['env'][key]
            ))
        requires = []
        for key in plugin['workspace']['requires'].keys():
            if key == 'apt':
                requires.append(DOCKERFILE_REQ_APT.format(
                    SRC=plugin['workspace']['requires'][key]
                ))
            elif key == 'pip':
                requires.append(DOCKERFILE_REQ_PIP.format(
                    SRC=plugin['workspace']['requires'][key]
                )) 

        # Dockerfile to memory
        dockerfile = DOCKERFILE.format(
            BASE=plugin['workspace']['base'],
            MAINTAINER=plugin['plugin']['maintainer'],
            ENVS='\n'.join(envs),
            PRESCRIPTS=';'.join(plugin['workspace']['prescripts']) if len(plugin['workspace']['prescripts']) else "echo .",
            REQUIRES='\n'.join(requires),
            POSTSCRIPTS=';'.join(plugin['workspace']['postscripts']) if len(plugin['workspace']['postscripts']) else "echo .",
            COMMAND='[{}]'.format(', '.join(
                [f'"{item}"' for item in plugin['workspace']['command'].split()] + 
                [f'"{item}"' for item in plugin['workspace']['arguments'].split()]
            )),
        )

        tarbytes = io.BytesIO()
        dockerfile_info = tarfile.TarInfo('.dockerfile')
        dockerfile_info.size = len(dockerfile)
        with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
            for name, arcname in utils.arcfiles(plugin['plugin']['workdir'], plugin['workspace']['ignore']):
                tar.add(name, arcname)
            tar.addfile(dockerfile_info, io.BytesIO(dockerfile.encode()))
        tarbytes.seek(0)

        # Build Image
        build_output = ctlr.build_image(cli, base_labels, tarbytes, dockerfile_info.name, no_cache, stream=True) 

    else:
        dockerfile = f"FROM {plugin['service']['image']}"

        tarbytes = io.BytesIO()
        dockerfile_info = tarfile.TarInfo('.dockerfile')
        dockerfile_info.size = len(dockerfile)
        with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
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

    #print(docker.auth.resolve_repository_name(base_labels['MLAD.PLUGIN.IMAGE']))
    repository, tag = base_labels['MLAD.PROJECT.IMAGE'].rsplit(':',1)
    # Check duplicated.
    tagged = False
    if latest_image != image:
        image.tag(repository, tag=image_version)
        tagged = True
        if latest_image and len(latest_image.tags) < 2 and latest_image.tags[-1].endswith(':latest'):
            latest_image.tag('remove')
            cli.images.remove('remove')
    else:
        if len(latest_image.tags) < 2:
            image.tag(repository, tag=image_version)
            tagged = True
        else:
            print('Already built plugin to image.', file=sys.stderr)

    if tagged:
        print(f"Built Image: {'/'.join(repository.split('/')[1:])}:{image_version}")

    # Upload Image
    #print('Update plugin image to registry...')
    #try:
    #    for _ in ctlr.push_images(cli, project_key, stream=True):
    #        if 'error' in _:
    #            raise docker.errors.APIError(_['error'], None)
    #        elif 'stream' in _:
    #            sys.stdout.write(_['stream'])
    #except docker.errors.APIError as e:
    #    print(e, file=sys.stderr)
    #    print('Failed to Update Image to Registry.', file=sys.stderr)
    #    print('Please Check Registry Server.', file=sys.stderr)
    #    sys.exit(1)
    #except StopIteration:
    #    pass

    print('Done.')

def installed(no_trunc):
    cli = ctlr.get_api_client()
    images = ctlr.get_images(cli, extra_labels=['MLAD.PROJECT.TYPE=plugin'])

    data = [('ID', 'REGISTRY', 'BUILD USER', 'PLUGIN NAME', 'MAINTAINER', 'VERSION', 'CREATED')]
    untagged = 0
    for _ in [ctlr.inspect_image(_) for _ in images]:
        if _['short_id'] == _['repository']:
            untagged += 1
            continue
        else:
            registry, builder = _['repository'].split('/', 1)
            if '.' in registry or ':' in registry:
                builder, __ = builder.split('/')
            else:
                builder = registry
                registry = 'docker.io'
            row = [
                _['short_id'],
                registry,
                builder,
                _['project_name'],
                _['maintainer'],
                f"[{_['tag']}]" if _['latest'] else f"{_['tag']}",
                _['created']
            ]
            data.append(row)
    utils.print_table(data, 'No have built image.')
    if untagged:
        print(f'This plugin has {untagged} untagged images. To free disk spaces up by cleaning gabage images.') 

def list(no_trunc):
    config = utils.read_config()
    projects = {}
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    networks = api.project.get(['MLAD.PROJECT.TYPE=plugin'])
    columns = [('USERNAME', 'PLUGIN', 'IMAGE', 'VERSION', 'EXPOSE', 'TASKS', 'AGE')]
    for network in networks:
        project_key = network['key']
        default = { 
            'username': network['username'], 
            'project': network['project'], 
            'image': network['image'],
            'version': network['version'],
            'expose': '',
            'node': '',
            'status': '',
            'age': '',
            'replicas': 0, 'services': 0, 'tasks': 0,
            
        }
        projects[project_key] = projects[project_key] if project_key in projects else default
        res = api.service.get(project_key=project_key)
        for inspect in res['inspects']:
            projects[project_key]['expose'] = inspect.get('ingress') or '-'
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
            columns.append((projects[project]['username'], projects[project]['project'], projects[project]['image'], projects[project]['version'], projects[project]['expose'], f"{running_tasks:>5}", projects[project]['age']))
        else:
            columns.append((projects[project]['username'], projects[project]['project'], projects[project]['image'], '-', '-', projects[project]['hostname'], projects[project]['workspace']))
    utils.print_table(columns, 'Cannot find running plugins.')

#def run(with_build):
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

def start(plugin_name, arguments):
    print('Deploying services to cluster...')

    config = utils.read_config()
    cli = ctlr.get_api_client()
    basename = f'{get_username(config)}-{plugin_name.lower()}-plugin'
    project_key = core_utils.project_key(basename)
    images = ctlr.get_images(cli, project_key=project_key)
    if not len(images):
        print('Not installed plugin [{plugin_name}].', file=sys.stderr)
        return

    # Get Base Labels
    base_labels = dict([(k, v) for k, v in images[0].labels.items() if k.startswith('MLAD.')])
    inspect = ctlr.inspect_image(images[0])
    target = json.loads(base64.urlsafe_b64decode(images[0].labels.get('MLAD.PROJECT.PLUGIN_MANIFEST').encode()).decode())
    target['name'] = plugin_name
    target['service_type'] = 'plugin'
    if arguments:
        target['arguments'] = f"{' '.join(arguments)}"

    # AuthConfig
    headers = {'auths': json.loads(base64.urlsafe_b64decode(ctlr.get_auth_headers(cli)['X-Registry-Config']))}
    encoded = base64.urlsafe_b64encode(json.dumps(headers).encode())
    credential = encoded.decode()
   
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    extra_envs = utils.get_service_env(default_config['client'](config))

    res = api.project.create({'name': '', 'version': '', 'author': ''}, base_labels,
        extra_envs, credential=credential, swarm=True, allow_reuse=False)
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
    if plugin_name in [_['name'] for _ in api.service.get(project_key)['inspects']]:
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

def stop(plugins):
    config = utils.read_config()
    api = API(utils.to_url(config.mlad), config.mlad.token.user)
    for plugin_name in plugins:
        basename = f'{get_username(config)}-{plugin_name.lower()}-plugin'
        project_key = core_utils.project_key(basename)

        # Block duplicated running.
        try:
            inspect = api.project.inspect(project_key=project_key)
        except NotFoundError as e:
            print(f'Already stopped plugin[{plugin_name}].', file=sys.stderr)
            continue

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

