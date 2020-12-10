import sys, os, copy, time
from pathlib import Path
import docker, requests
from docker.types import LogConfig
from mladcli.libs import utils, interrupt_handler as InterruptHandler, logger_thread as LoggerThread

HOME = str(Path.home())
CONFIG_PATH = HOME + '/.mlad'
SHORT_LEN = 10

# Docker CLI from HOST
def getDockerCLI(lowlevel=False):
    config = utils.read_config()
    if not lowlevel:
        return docker.from_env(environment={'DOCKER_HOST': config['docker']['host']})
    else:
        return docker.APIClient(config['docker']['host'])

# Image
def image_list(project=None):
    config = utils.read_config()

    filters = 'MLAD.PROJECT'
    if project: filters+= f"={utils.getProjecteName(projecet)}"

    cli = getDockerCLI()
    images = cli.images.list(filters={ 'label': filters } )

    dummies = 0
    data = []
    for image in images:
        if image.tags:
            head = max([ tag.endswith('latest') for tag in image.tags ])
            repository, tag = sorted(image.tags)[0].rsplit(':', 1)
            data.append((
                image.short_id[-SHORT_LEN:], 
                repository,
                tag,
                head,
                image.labels['MLAD.PROJECT.NAME'], 
                image.attrs['Author'], 
                image.attrs['Created'], 
            ))
        else:
            dummies += 1
    return data, dummies

def image_build(project, workspace, tagging=False, verbose=False):
    config = utils.read_config()
    project_name = utils.getProjectName(project)
    project_version=project['version'].lower()
    repository = utils.getRepository(project)
    latest_name = f'{repository}:latest'

    PROJECT_CONFIG_PATH = utils.getProjectConfigPath(project)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'
    DOCKERIGNORE_FILE = utils.getWorkingDir() + '/.dockerignore'

    cli = getDockerCLI()
    llcli = getDockerCLI(True)

    # Block duplicated running.
    #filters = 'MLAD.PROJECT=%s' % project_name
    #if len(cli.services.list(filters={'label': filters})):
    #    print('Need to down running project.', file=sys.stderr)
    #    sys.exit(1)

    # Check latest image
    latest_image = None
    commit_number = 1
    images = cli.images.list(filters={'label': f'MLAD.PROJECT={project_name}'})
    if len(images):
        latest_image = sorted(filter(None, [ image if tag.endswith('latest') else None for image in images for tag in image.tags ]), key=lambda x: str(x))
        if latest_image and len(latest_image): latest_image = latest_image[0]
        tags = sorted(filter(None, [ tag if not tag.endswith('latest') else None for image in images for tag in image.tags ]))
        if len(tags): commit_number=int(tags[-1].split('.')[-1])+1
    image_version = f'{project_version}.{commit_number}'

    # Generate dockerignore
    with open(DOCKERIGNORE_FILE, 'w') as f:
        f.write('\n'.join(workspace['ignore']))

    # Docker build
    try:
        build_output = llcli.build(
            path=utils.getWorkingDir(),
            tag=latest_name,
            dockerfile=DOCKERFILE_FILE,
            labels={
                'MLAD.PROJECT': project_name,
                'MLAD.PROJECT.NAME': project['name'].lower(),
                'MLAD.PROJECT.USERNAME': config['account']['username'],
                'MLAD.PROJECT.VERSION': project_version
            },
            forcerm=True,
            decode=True
        )
        try:
            image = (cli.images.get(latest_name), build_output)
        except docker.errors.APIError:
            image = (None, build_output)

        #image = cli.images.build(
        #    path=utils.getWorkingDir(),
        #    tag=latest_name,
        #    dockerfile=DOCKERFILE_FILE,
        #    labels={
        #        'MLAD.PROJECT': project_name,
        #        'MLAD.PROJECT.NAME': project['name'].lower(),
        #        'MLAD.PROJECT.USERNAME': config['account']['username'],
        #        'MLAD.PROJECT.VERSION': project_version
        #    },
        #    rm=True
        #)

        # Print build output
        for _ in image[1]:
            if 'error' in _:
                raise docker.errors.BuildError(_['error'], None)
            elif 'stream' in _:
                if verbose: sys.stdout.write(_['stream'])

    except docker.errors.BuildError as e:
        print(e, file=sys.stderr)
        # Remove dockerignore
        os.unlink(DOCKERIGNORE_FILE)
        sys.exit(1)
    except docker.errors.APIError as e:
        print(e, file=sys.stderr)
        # Remove dockerignore
        os.unlink(DOCKERIGNORE_FILE)
        sys.exit(1)

    # Remove dockerignore
    os.unlink(DOCKERIGNORE_FILE)

    # Check duplicated.
    tagged = False
    if latest_image != image[0]:
        if tagging:
            image[0].tag(repository, tag=image_version)
            tagged = True
        if latest_image and len(latest_image.tags) < 2 and latest_image.tags[-1].endswith(':latest'):
            latest_image.tag('remove')
            cli.images.remove('remove')
    else:
        if tagging and len(latest_image.tags) < 2:
            image[0].tag(repository, tag=image_version)
            tagged = True
        else:
            print('Already built project to image.', file=sys.stderr)

    if tagged:
        return f"{'/'.join(repository.split('/')[1:])}:{image_version}"
    else:
        return None

def image_remove(ids, force):
    config = utils.read_config()
    cli = getDockerCLI()
    result = [ cli.images.remove(image=id, force=force) for id in ids ]
    return result

def image_prune(project):
    config = utils.read_config()

    cli = getDockerCLI()
    if project:
        filters = 'MLAD.PROJECT'
        if project: filters+= f'={utils.getProjectName(project)}'

        images = cli.images.list(filters={ 'label': filters } )

        count = 0
        for image in images:
            if not image.tags:
                cli.images.remove(image=image.id, force=False)
                count += 1
        return count 
    else:
        return cli.images.prune(filters={ 'dangling': True })

def image_push(project):
    config = utils.read_config()
    project_name = utils.getProjectName(project)
    project_version=project['version'].lower()
    repository = utils.getRepository(project)
    
    cli = getDockerCLI()
    try:
        for _ in cli.images.push(repository, stream=True, decode=True):
            if 'error' in _:
                raise docker.errors.APIError(_['error'], None)
            elif 'stream' in _:
                sys.stdout.write(_['stream'])
    except docker.errors.APIError as e:
        print(e, file=sys.stderr)
        print('Failed to Update Image to Registry.', file=sys.stderr)
        print('Please Check Registry Server.', file=sys.stderr)
        sys.exit(1)
    
# Project
def running_projects():
    config = utils.read_config()

    filters = 'MLAD.PROJECT'

    cli = getDockerCLI()
    services = cli.services.list(filters={'label': filters})
    data = {}
    if len(services):
        for service in services:
            project = service.attrs['Spec']['Labels']['MLAD.PROJECT.NAME']
            replicas = service.attrs['Spec']['Mode']['Replicated']['Replicas']
            image = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image']
            username = service.attrs['Spec']['Labels']['MLAD.PROJECT.USERNAME']
            data[project] = data[project] if project in data else { 'username': username,'image': image, 'services': 0 }
            data[project]['services'] += replicas

    return data

def images_up(project, services, by_service=False):
    from mladcli.default import project_service as service_default

    config = utils.read_config()

    project_name = utils.getProjectName(project)
    project_version=project['version'].lower()
    repository = utils.getRepository(project)
    image_name = f'{repository}:latest'
    project_id = utils.generate_unique_id()
    wait_queue = list(services.keys())
    running_queue = []

    cli = getDockerCLI()
 
    # Block duplicated running.
    skip_create_network = False
    if not project['partial']:
        filters = f'MLAD.PROJECT={project_name}'
        if len(cli.services.list(filters={'label': filters})):
            print('Already running project.', file=sys.stderr)
            sys.exit(1)
    else:
        for service_name in services:
            filters = [f'MLAD.PROJECT={project_name}', f'MLAD.PROJECT.SERVICE={service_name}']
            if len(cli.services.list(filters={'label': filters})):
                print(f'Already running service[{service_name}] in project.', file=sys.stderr)
                sys.exit(1)

        running_services = cli.services.list(filters={'label': f'MLAD.PROJECT={project_name}'})
        if len(running_services): 
            skip_create_network = True
            project_id = running_services[0].attrs['Spec']['Labels'].get('MLAD.PROJECT.ID', project_id)

    with InterruptHandler(message='Wait.', blocked=True):
        # Create Docker Network
        networks = [ 
            f'{project_name}_backend_{"overlay" if by_service else "bridge"}'
        ]
        if not skip_create_network:
            for network in networks:
                try:
                    instance = cli.networks.get(network)
                    if instance: 
                        print('Clear already created network.', file=sys.stderr)
                        instance.remove()
                        time.sleep(1)
                except docker.errors.APIError as e:
                    pass
                try:
                    print('Create network...')
                    if by_service:
                        for _ in range(0, 255, 4):
                            subnet = f'10.0.{_}.0/22'
                            ipam_pool = docker.types.IPAMPool(subnet=subnet)
                            ipam_config = docker.types.IPAMConfig(pool_configs=[ipam_pool])
                            net = cli.networks.create(network, driver='overlay', ipam=ipam_config, ingress='frontend' in network)
                            if net.attrs['Driver']: 
                                print(f'Selected Subnet [{subnet}]')
                                break
                            net.remove()
                    else:
                        cli.networks.create(network, driver='bridge')
                except docker.errors.APIError as e:
                    print('Failed to create network.', file=sys.stderr)
                    print(e, file=sys.stderr)

    with InterruptHandler(blocked=True) as h:
        # Create Docker Service
        pending_instance = None
        while not h.interrupted and (len(wait_queue) or pending_instance):
            # Check Pending instances
            if pending_instance:
                service_name, expired = pending_instance
                inst_name = f'{project_name}_{service_name}'
                if by_service:
                    instance = cli.services.get(inst_name)
                    tasks = instance.tasks()
                    #running = min([task['Status']['State'] == 'running' for task in tasks ])
                    running = min([task['DesiredState'] == 'running' for task in tasks ])
                    status = 'running' if running else 'preparing'
                else:
                    instance = cli.containers.get(inst_name)
                    status = instance.status
                #print(status)
                if status == 'running':
                    print('[RUNNING]')
                    running_queue.append(service_name)
                    pending_instance = None
                elif expired < time.time():
                    print('[FAILED]', file=sys.stderr)
                    show_logs(project, 'all', False, False, [], by_service)
                    sys.exit(1)
                else:
                    time.sleep(1)
                    continue
            if not len(wait_queue): break

            # Get item in wait queue
            service_key = wait_queue.pop(0)
            service = service_default(services[service_key])

            # Check dependencies
            requeued = False
            if pending_instance:
                requeued = True
            else:
                for depend in service['depends']:
                    if not depend in running_queue:
                        wait_queue.append(service_key)
                        requeued = True
                        break

            if not requeued:
                # Define specs and resources
                BUCKET_PATH = f"{config['account']['username']}/{project['name'].lower()}/"
                service_name = service_key.lower()
                image = service['image'] or image_name
                env = utils.get_service_env()
                env += [f"TF_CPP_MIN_LOG_LEVEL=3"]
                env += [f"PROJECT={project['name'].lower()}"]
                env += [f"PROJECT_ID={project_id}"]
                env += [f"SERVICE={service_name}"]
                env += [f"USERNAME={config['account']['username']}"]
                #env += [ 'OUTDIR=s3://models/{}'.format(BUCKET_PATH) ]
                #env += [ 'LOGDIR=s3://logs/{}'.format(BUCKET_PATH) ]
                #env += [ 'DATADIR=s3://data/{}'.format('') ]
                env += [ f"{key}={service['env'][key]}" for key in service['env'].keys() ]
                command = service['command'] + service['arguments']
                labels = {
                    'MLAD.PROJECT': project_name, 
                    'MLAD.PROJECT.ID': project_id,
                    'MLAD.PROJECT.NAME': project['name'].lower(), 
                    'MLAD.PROJECT.SERVICE': service_name,
                    'MLAD.PROJECT.USERNAME': config['account']['username']
                }
                
                policy = service['deploy']['restart_policy']
                # Convert Human-readable to nanoseconds ns|us|ms|s|m|h
                if policy['delay']:
                    converted = policy['delay']
                    timeinfo = str(converted).lower()
                    if timeinfo.endswith('ns'):
                        converted = int(timeinfo[:-2]) * 1
                    elif timeinfo.endswith('us'):
                        converted = int(timeinfo[:-2]) * 1000
                    elif timeinfo.endswith('ms'):
                        converted = int(timeinfo[:-2]) * 1000000
                    elif timeinfo.endswith('s'):
                        converted = int(timeinfo[:-1]) * 1000000000
                    elif timeinfo.endswith('m'):
                        converted = int(timeinfo[:-1]) * 1000000000 * 60
                    elif timeinfo.endswith('h'):
                        converted = int(timeinfo[:-1]) * 1000000000 * 60 * 60
                    policy['delay'] = converted
                if policy['window']:
                    converted = policy['window']
                    timeinfo = str(converted).lower()
                    if timeinfo.endswith('ns'):
                        converted = int(timeinfo[:-2]) * 1
                    elif timeinfo.endswith('us'):
                        converted = int(timeinfo[:-2]) * 1000
                    elif timeinfo.endswith('ms'):
                        converted = int(timeinfo[:-2]) * 1000000
                    elif timeinfo.endswith('s'):
                        converted = int(timeinfo[:-1]) * 1000000000
                    elif timeinfo.endswith('m'):
                        converted = int(timeinfo[:-1]) * 1000000000 * 60
                    elif timeinfo.endswith('h'):
                        converted = int(timeinfo[:-1]) * 1000000000 * 60 * 60
                    policy['window'] = converted

                restart_policy = docker.types.RestartPolicy(
                    condition=policy['condition'], 
                    delay=policy['delay'], 
                    max_attempts=policy['max_attempts'], 
                    window=policy['window']
                )
                resources = docker.types.Resources()
                service_mode = docker.types.ServiceMode('replicated')
                constraints = []
                if by_service:
                    res_spec = {}
                    if 'cpus' in service['deploy']['quotes']: 
                        res_spec['cpu_limit'] = service['deploy']['quotes']['cpus'] * 1000000000
                        res_spec['cpu_reservation'] = service['deploy']['quotes']['cpus'] * 1000000000
                    if 'mems' in service['deploy']['quotes']: 
                        data = str(service['deploy']['quotes']['mems'])
                        size = int(data[:-1])
                        unit = data.lower()[-1:]
                        if unit == 'g':
                            size *= (2**30)
                        elif unit == 'm':
                            size *= (2**20)
                        elif unit == 'k':
                            size *= (2**10)
                        res_spec['mem_limit'] = size
                        res_spec['mem_reservation'] = size
                    if 'gpus' in service['deploy']['quotes']:
                        if service['deploy']['quotes']['gpus'] > 0:
                            res_spec['generic_resources'] = { 'gpu': service['deploy']['quotes']['gpus'] }
                        else: 
                            #res_spec['generic_resources'] = { 'gpu': service['deploy']['quotes']['gpus'] }
                            env += [ 'NVIDIA_VISIBLE_DEVICES=void' ]
                    resources = docker.types.Resources(**res_spec)
                    service_mode = docker.types.ServiceMode('replicated', replicas=service['deploy']['replicas'])
                    constraints = [
                        f"node.{key}=={str(service['deploy']['constraints'][key])}" for key in service['deploy']['constraints']
                    ]

                # Try to run
                inst_name = f'{project_name}_{service_name}'
                print(f'Start {inst_name}...', end=' ')
                if not by_service:
                    try:
                        instance = cli.containers.get(inst_name)
                        if instance:
                            instance.stop()
                            instance.remove()
                    except docker.errors.NotFound as e:
                        pass
                    instance = cli.containers.run(
                        image, 
                        command=command,
                        name=inst_name,
                        environment=env,
                        labels=labels,
                        runtime='runc',
                        restart_policy={'Name': 'on-failure', 'MaximumRetryCount': 1},
                        detach=True,
                    )
                    for network_name in networks:
                        network = cli.networks.get(network_name)
                        network.connect(instance, aliases=[service_name])
                else:
                    try:
                        instance = cli.services.get(inst_name)
                        if instance:
                            instance.remove()
                    except docker.errors.NotFound as e:
                        pass
                    instance = cli.services.create(
                        name=inst_name,
                        #hostname=f'{service_name}.{{{{.Task.Slot}}}}',
                        image=image, 
                        env=env + ['TASK_ID={{.Task.ID}}', f'TASK_NAME={service_name}.{{{{.Task.Slot}}}}', 'NODE_HOSTNAME={{.Node.Hostname}}'],
                        mounts=['/etc/timezone:/etc/timezone:ro', '/etc/localtime:/etc/localtime:ro'],
                        command=command,
                        container_labels=labels,
                        labels=labels,
                        networks=[{'Target': network, 'Aliases': [service_name]} for network in networks ],
                        restart_policy=restart_policy,
                        resources=resources,
                        mode=service_mode,
                        constraints=constraints
                    )
                pending_instance = (service_name, time.time() + 3600)
            time.sleep(1)
        if h.interrupted:
            return None
    return project_name
            
def show_logs(project, tail='all', follow=False, timestamps=False, services=[], by_service=False):
    project_name = utils.getProjectName(project)
    project_version=project['version'].lower()
    config = utils.read_config()

    def task_logger(id, **params):
        with requests.get(f"http://{config['docker']['host']}/v1.24/tasks/{id}/logs", params=params, stream=True) as resp:
            for iter in resp.iter_content(0x7FFFFFFF):
                out = iter[docker.constants.STREAM_HEADER_SIZE_BYTES:].decode('utf8')
                if timestamps:
                    temp = out.split(' ')
                    out = ' '.join([temp[1], temp[0]] + temp[2:])
                yield out.encode('utf8')
                #yield iter[docker.constants.STREAM_HEADER_SIZE_BYTES:] 
        return ''

    cli = getDockerCLI()
    with InterruptHandler() as h:
        if by_service:
            instances = cli.services.list(filters={'label': f'MLAD.PROJECT={project_name}'})
            if not utils.is_host_wsl2() and not config['docker']['host'].startswith('unix://'):
                logs = [ (inst.attrs['Spec']['Labels']['MLAD.PROJECT.SERVICE'], task_logger(task['ID'], details=True, follow=follow, tail=tail, timestamps=timestamps, stdout=True, stderr=True)) for inst in instances for task in inst.tasks() ]
            else:
                logs = [ (inst.attrs['Spec']['Labels']['MLAD.PROJECT.SERVICE'], inst.logs(details=True, follow=follow, tail=tail, timestamps=timestamps, stdout=True, stderr=True)) for inst in instances ]
        else:
            instances = cli.containers.list(all=True, filters={'label': f'MLAD.PROJECT={project_name}'})
            timestamps = True
            logs = [ (inst.attrs['Config']['Labels']['MLAD.PROJECT.SERVICE'], inst.logs(follow=follow, tail=tail, timestamps=timestamps, stream=True)) for inst in instances ]

        if len(logs):
            name_width = min(32, max([len(name) for name, _ in logs]))
            loggers = [ LoggerThread(name, name_width, log, services, by_service, timestamps, SHORT_LEN) for name, log in logs ]
            for logger in loggers: logger.start()
            while not h.interrupted and max([ not logger.interrupted for logger in loggers ]):
                time.sleep(0.01)
            for logger in loggers: logger.interrupt()
        else:
            print('Cannot find running project.', file=sys.stderr)

def images_down(project, services, by_service=False):
    config = utils.read_config()
    project_name = utils.getProjectName(project)

    cli = getDockerCLI()

    # Block duplicated running.
    if not project['partial']:
        filters = f'MLAD.PROJECT={project_name}'
        if not len(cli.services.list(filters={'label': filters})):
            print('Already stopped project.', file=sys.stderr)
            sys.exit(1)
    else:
        for service_name in services:
            filters = [f'MLAD.PROJECT={project_name}', f'MLAD.PROJECT.SERVICE={service_name}']
            if not len(cli.services.list(filters={'label': filters})):
                print(f'Already stopped service[{service_name}] in project.', file=sys.stderr)
                sys.exit(1)

    with InterruptHandler(message='Wait.', blocked=True):
        drop_with_network = True
        if by_service:
            #services = cli.services.list(filters={'label': 'MLAD.PROJECT=%s'%project_name})
            down_services = []
            for service_name in services:
                filters = [f'MLAD.PROJECT={project_name}', f'MLAD.PROJECT.SERVICE={service_name}']
                down_services += cli.services.list(filters={'label': filters})
            if len(down_services):
                for service in down_services:
                    print(f'Stop {service.name}...')
                    service.remove()
            else:
                print('Cannot find running services.', file=sys.stderr)
            if len(cli.services.list(filters={'label': f'MLAD.PROJECT={project_name}'})) > 0:
                drop_with_network = False
        else:
            containers = cli.containers.list(filters={'label': f'MLAD.PROJECT={project_name}'})
            if len(containers):
                for container in containers:
                    print(f'Stop {container.name}...')
                    container.stop()
                for container in containers:
                    container.wait()
                    container.remove()
            else:
                print('Cannot find running containers.', file=sys.stderr)

        if drop_with_network:
            networks = [ 
                f'{project_name}_backend_{"overlay" if by_service else "bridge"}'
            ]
            for network in networks:
                try:
                    instance = cli.networks.get(network)
                    instance.remove()
                    print('Network removed.')
                except docker.errors.APIError as e:
                    print('Network already removed.', file=sys.stderr)

def show_status(project, services, all=False):
    project_name = utils.getProjectName(project)

    inst_names = []
    for key in services.keys():
        inst_names.append(f'{project_name}_{key.lower()}')
    
    cli = getDockerCLI()

    # Block not running.
    filters = f'MLAD.PROJECT={project_name}'
    if not len(cli.services.list(filters={'label': filters})):
        print('Cannot running service.', file=sys.stderr)
        sys.exit(1)

    task_info = []
    for inst_name in inst_names:
        try:
            instance = cli.services.get(inst_name)
            name = instance.attrs['Spec']['Labels']['MLAD.PROJECT.NAME']
            username = instance.attrs['Spec']['Labels']['MLAD.PROJECT.USERNAME']
            service = instance.attrs['Spec']['Labels']['MLAD.PROJECT.SERVICE']
            tasks = instance.tasks()
            for task in tasks:
                if all or task['Status']['State'] not in ['shutdown', 'failed']:
                    task_info.append((
                        task['ID'][:SHORT_LEN],
                        name, 
                        username,
                        service,
                        cli.nodes.get(task['NodeID']).attrs['Description']['Hostname'] if 'NodeID' in task else '-',
                        task['DesiredState'], 
                        task['Status']['State'], 
                        task['Status']['Err'] if 'Err' in task['Status'] else '-')
                    )
        except docker.errors.NotFound as e:
            pass
    
    return task_info
    
def scale_service(project, scale_spec):
    project_name = utils.getProjectName(project)
    
    cli = getDockerCLI()
    
    # Block not running.
    filters = f'MLAD.PROJECT={project_name}'
    if not len(cli.services.list(filters={'label': filters})):
        print('Cannot running service.', file=sys.stderr)
        sys.exit(1)
    
    for service_name in scale_spec:
        try:
            service = cli.services.get(f'{project_name}_{service_name}')

            if service.scale(int(scale_spec[service_name])):
                print(f'Change scale service [{service_name}].')
            else:
                print(f'Failed to change scale service [{service_name}].')

        except docker.errors.NotFound:
            print(f'Cannot find service [{service_name}].', file=sys.stderr)

def node_list():
    cli = getDockerCLI()
    return cli.nodes.list()

def node_enable(id):
    cli = getDockerCLI()
    try:
        node = cli.nodes.get(id)
    except docker.errors.APIError as e:
        print(f'Cannot find node "{id}"', file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'active'
    node.update(spec)
    
def node_disable(id):
    cli = getDockerCLI()
    try:
        node = cli.nodes.get(id)
    except docker.errors.APIError as e:
        print(f'Cannot find node "{id}"', file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'drain'
    node.update(spec)
    
def node_label_add(id, **kv):
    cli = getDockerCLI()
    try:
        node = cli.nodes.get(id)
    except docker.errors.APIError as e:
        print(f'Cannot find node "{id}"', file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    for key in kv:
        spec['Labels'][key] = kv[key]
    node.update(spec)

def node_label_rm(id, *keys):
    cli = getDockerCLI()
    try:
        node = cli.nodes.get(id)
    except docker.errors.APIError as e:
        print(f'Cannot find node "{id}"', file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    for key in keys:
        del spec['Labels'][key]
    node.update(spec)

