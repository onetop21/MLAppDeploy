import sys, os, copy, time, datetime
from pathlib import Path
import docker
from MLAppDeploy.libs import utils, interrupt_handler as InterruptHandler, logger_thread as LoggerThread

HOME = str(Path.home())
CONFIG_PATH = HOME + '/.mlad'
PROJECT_PATH = os.getcwd()
SHORT_LEN = 10

# Docker CLI from HOST
def getDockerCLI():
    config = utils.read_config()
    return docker.from_env(environment={'DOCKER_HOST':'%s'%config['docker']['host']})

# Image
def image_list(project=None):
    config = utils.read_config()

    filters = 'MLAD.PROJECT'
    if project: filters+= '=%s' % project['name'].lower()

    cli = getDockerCLI()
    images = cli.images.list(filters={ 'label': filters } )

    data = []
    for image in images:
        head = max([ tag.endswith('latest') for tag in image.tags ])
        repository, tag = sorted(image.tags)[0].rsplit(':', 1)
        data.append((
            image.short_id[-SHORT_LEN:], 
            repository,
            tag,
            head,
            image.labels['MLAD.PROJECT'], 
            image.attrs['Author'], 
            image.attrs['Created'], 
        ))
    return data

def image_build(project, workspace, tagging=False):
    config = utils.read_config()
    project_name = project['name'].lower()
    project_version=project['version'].lower()
    repository = '{REPO}/{OWNER}/{NAME}'.format(
        REPO=config['docker']['registry'],
        OWNER=config['account']['username'],
        NAME=project_name,
    )
    latest_name = '{REPOSITORY}:latest'.format(REPOSITORY=repository)

    PROJECT_CONFIG_PATH = '%s/%s'%(CONFIG_PATH, project_name)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'
    DOCKERIGNORE_FILE = PROJECT_PATH + '/.dockerignore'

    cli = getDockerCLI()

    # Check latest image
    latest_image = None
    commit_number = 1
    images = cli.images.list(filters={'label': 'MLAD.PROJECT=%s'%project_name})
    if len(images):
        latest_image = sorted(filter(None, [ image if tag.endswith('latest') else None for image in images for tag in image.tags ]), key=lambda x: str(x))
        if latest_image and len(latest_image): latest_image = latest_image[0]
        tags = sorted(filter(None, [ tag if not tag.endswith('latest') else None for image in images for tag in image.tags ]))
        if len(tags): commit_number=int(tags[-1].split('.')[-1])+1
    image_version = '%s.%d'%(project_version, commit_number)

    # Generate dockerignore
    with open(DOCKERIGNORE_FILE, 'w') as f:
        f.write('\n'.join(workspace['ignore']))

    # Docker build
    try:
        image = cli.images.build(
            path=PROJECT_PATH,
            tag=latest_name,
            dockerfile=DOCKERFILE_FILE,
            labels={
                'MLAD.PROJECT': project_name,
                'MLAD.PROJECT.VERSION': project_version
            },
            rm=True
        )
    except docker.errors.BuildError as e:
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
        return '%s:%s'%('/'.join(repository.split('/')[1:]), image_version) 
    else:
        return None

def image_remove(ids, force):
    config = utils.read_config()
    cli = getDockerCLI()
    result = [ cli.images.remove(image=id, force=force) for id in ids ]
    return result

def image_prune(project, strong):
    config = utils.read_config()
    
    filters = 'MLAD.PROJECT'
    if project: filters+= '=%s' % project['name'].lower()

    cli = getDockerCLI()
    return cli.images.prune(filters={ 'dangling': not strong, 'label': filters } )

def image_push(project):
    config = utils.read_config()
    project_name = project['name'].lower()
    project_version=project['version'].lower()
    repository = '{REPO}/{OWNER}/{NAME}'.format(
        REPO=config['docker']['registry'],
        OWNER=config['account']['username'],
        NAME=project_name,
    )
    
    cli = getDockerCLI()
    try:
        cli.images.push(repository)
        return True
    except docker.errors.APIError as e:
        print('Failed to Update Image to Registry.', file=sys.stderr)
        print('Please Check Registry Server.', file=sys.stderr)
        return False
    

# Project
def running_projects():
    config = utils.read_config()

    filters = 'MLAD.PROJECT'

    cli = getDockerCLI()
    services = cli.services.list(filters={'label': filters})
    data = {}
    if len(services):
        for service in services:
            project = service.attrs['Spec']['Labels'][filters]
            replicas = service.attrs['Spec']['Mode']['Replicated']['Replicas']
            image = service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image']
            data[project] = data[project] if project in data else { 'image': image, 'replicas': 0 }
            data[project]['replicas'] += replicas

        print('{:24} {:48} {:8}'.format('PROJECT', 'IMAGE', 'REPLICAS'))
        for project in data:
            print('{:24} {:48} {:8}'.format(project, data[project]['image'], data[project]['replicas']))
    else:
        print('Cannot find running project.', file=sys.stderr)
        sys.exit(1)

def images_up(project, services, by_service=False):
    import MLAppDeploy.default as default

    config = utils.read_config()

    project_name = project['name'].lower()
    project_version=project['version'].lower()
    repository = '{REPO}/{OWNER}/{NAME}'.format(
        REPO=config['docker']['registry'],
        OWNER=config['account']['username'],
        NAME=project_name,
    )
    image_name = '{REPOSITORY}:latest'.format(REPOSITORY=repository)
   
    wait_queue = list(services.keys())
    running_queue = []

    cli = getDockerCLI()
 
    # Block duplicated running.
    if by_service:
        filters = 'MLAD.PROJECT=%s' % project_name
        if len(cli.services.list(filters={'label': filters})):
            print('Already running project.', file=sys.stderr)
            sys.exit(1)

    with InterruptHandler(message='Wait.', blocked=True):
        # Create Docker Network
        networks = [ 
            '%s_%s_backend_%s' % (config['account']['username'], project_name, 'overlay' if by_service else 'bridge'),
        ]
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
                    cli.networks.create(network, driver='overlay', ingress='frontend' in network)
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
                inst_name='{PROJECT}_{SERVICE}'.format(PROJECT=project_name, SERVICE=service_name)
                if by_service:
                    instance = cli.services.get(inst_name)
                    tasks = instance.tasks()
                    #running = min([task['Status']['State'] == 'running' for task in tasks ])
                    running = min([task['DesiredState'] == 'running' for task in tasks ])
                    status = 'running' if running else 'preparing'
                else:
                    instance = cli.containers.get(inst_name)
                    status = instance.status
                if status == 'running':
                    print('[RUNNING]')
                    running_queue.append(service_name)
                    pending_instance = None
                elif expired < time.time():
                    print('[FAILED]', file=sys.stderr)
                    show_logs(project, 'all', False, by_service)
                    sys.exit(1)
                else:
                    time.sleep(1)
                    continue
            if not len(wait_queue): break

            # Get item in wait queue
            service_key = wait_queue.pop(0)
            service = default.project_service(services[service_key])

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
                service_name = service_key.lower()
                image = service['image'] or image_name
                env = [ '{KEY}={VALUE}'.format(KEY=key, VALUE=service['env'][key]) for key in service['env'].keys() ]
                env += [ 'SERVICENAME={}'.format(service_name) ]
                command = service['command'] + service['arguments']
                labels = {'MLAD.PROJECT': project_name}
                
                restart_policy = docker.types.RestartPolicy()
                resources = docker.types.Resources()
                service_mode = docker.types.ServiceMode('replicated')
                constraints = []
                if by_service:
                    resources = docker.types.Resources(
                        cpu_limit=service['deploy']['quotes']['cpus'] * 1000000000,
                        cpu_reservation=service['deploy']['quotes']['cpus'] * 1000000000
                    )
                    if service['deploy']['quotes']['gpus']: resources['generic-resources'] = { 'gpu': service['deploy']['quotes']['gpus'] }
                    service_mode = docker.types.ServiceMode('replicated', replicas=service['deploy']['replicas'])
                    constraints = [ '{KEY}={VALUE}'.format(KEY=key, VALUE=service['deploy']['constraints'][key]) for key in service['deploy']['constraints'] ]

                # Try to run
                inst_name='{PROJECT}_{SERVICE}'.format(PROJECT=project_name, SERVICE=service_name)
                print('Start %s...' % inst_name, end=' ')
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
                        image=image, 
                        env=env,
                        command=command,
                        container_labels=labels,
                        labels=labels,
                        networks=[{'Target': network, 'Aliases': [ service_name ]} for network in networks ],
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
            
def show_logs(project, tail='all', follow=False, by_service=False):
    project_name = project['name'].lower()
    project_version=project['version'].lower()

    cli = getDockerCLI()
    with InterruptHandler() as h:
        if by_service:
            instances = cli.services.list(filters={'label': 'MLAD.PROJECT=%s'%project_name})
            logs = [ (instance.name, instance.logs(details=True, follow=follow, tail=tail, stdout=True, stderr=True)) for instance in instances ]
        else:
            instances = cli.containers.list(all=True, filters={'label': 'MLAD.PROJECT=%s'%project_name})
            logs = [ (instance.name, instance.logs(follow=follow, tail=tail, stream=True)) for instance in instances ]

        if len(logs):
            name_width = min(32, max([len(inst[0]) for inst in logs]))
            loggers = [ LoggerThread(name, name_width, log, by_service, SHORT_LEN) for name, log in logs ]
            for logger in loggers: logger.start()
            while not h.interrupted and max([ not logger.interrupted for logger in loggers ]):
                time.sleep(0.01)
            for logger in loggers: logger.interrupt()
        else:
            print('Cannot find running project.', file=sys.stderr)

def images_down(project, by_service=False):
    config = utils.read_config()
    project_name = project['name'].lower()

    cli = getDockerCLI()

    # Block not running.
    if by_service:
        filters = 'MLAD.PROJECT=%s' % project_name
        if not len(cli.services.list(filters={'label': filters})):
            print('Cannot running service.', file=sys.stderr)
            sys.exit(1)

    with InterruptHandler(message='Wait.', blocked=True):
        if by_service:
            services = cli.services.list(filters={'label': 'MLAD.PROJECT=%s'%project_name})
            if len(services):
                for service in services:
                    print('Stop %s...'%service.name)
                    service.remove()
            else:
                print('Cannot find running services.', file=sys.stderr)
        else:
            containers = cli.containers.list(filters={'label': 'MLAD.PROJECT=%s'%project_name})
            if len(containers):
                for container in containers:
                    print('Stop %s...'%container.name)
                    container.stop()
            else:
                print('Cannot find running containers.', file=sys.stderr)
        networks = [ 
            '%s_%s_backend_%s' % (config['account']['username'], project_name, 'overlay' if by_service else 'bridge'),
        ]
        for network in networks:
            try:
                instance = cli.networks.get(network)
                instance.remove()
                print('Network removed.')
            except docker.errors.APIError as e:
                print('Network already removed.', file=sys.stderr)

def show_status(project, services):
    project_name = project['name'].lower()
    inst_names = []
    for key in services.keys():
        inst_names.append('{PROJECT}_{SERVICE}'.format(PROJECT=project_name, SERVICE=key.lower()))
    
    cli = getDockerCLI()

    # Block not running.
    filters = 'MLAD.PROJECT=%s' % project_name
    if not len(cli.services.list(filters={'label': filters})):
        print('Cannot running service.', file=sys.stderr)
        sys.exit(1)

    task_info = []
    for inst_name in inst_names:
        try:
            instance = cli.services.get(inst_name)
            tasks = instance.tasks()
            for task in tasks:
                task_info.append(
                    ('{}.{}'.format(inst_name, task['ID'][:SHORT_LEN]), 
                    cli.nodes.get(task['NodeID']).attrs['Description']['Hostname'], 
                    task['DesiredState'], 
                    task['Status']['State'], 
                    task['Status']['Err'] if 'Err' in task['Status'] else '-')
                )
        except docker.errors.NotFound as e:
            pass
    
    if len(task_info):
        print('{:32} {:16} {:16} {:16} {:16}'.format('NAME', 'NODE', 'DESIRED STATE', 'CURRENT STATE', 'ERROR'))
        for name, node, desired_state, current_state, error in task_info:
            print('{:32} {:16} {:16} {:16} {:16}'.format(name, node, desired_state, current_state, error))
    else:
        print('Project is not running.', file=sys.stderr)
        sys.exit(1)

def scale_service(project, scale_spec):
    project_name = project['name'].lower()
    
    cli = getDockerCLI()
    
    # Block not running.
    filters = 'MLAD.PROJECT=%s' % project_name
    if not len(cli.services.list(filters={'label': filters})):
        print('Cannot running service.', file=sys.stderr)
        sys.exit(1)
    
    for srervice_name in scale_spec:
        try:
            service = cli.services.get(service_name)

            if service.scale(scale_spec[service_name]):
                print('Change scale service [%s].' % service_name)
            else:
                print('Failed to change scale service [%s].' % service_name)

        except docker.errors.NotFound:
            print('Cannot find service [%s].' % service_name, file=sys.stderr)

def node_list():
    cli = getDockerCLI()
    return cli.nodes.list()

def node_enable(id):
    cli = getDockerCLI()
    try:
        node = cli.nodes.get(id)
    except docker.errors.APIError as e:
        print('Cannot find node "%s"' % name, file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'active'
    node.update(spec)
    
def node_disable(id):
    cli = getDockerCLI()
    try:
        node = cli.nodes.get(id)
    except docker.errors.APIError as e:
        print('Cannot find node "%s"' % name, file=sys.stderr)
        sys.exit(1)
    spec = node.attrs['Spec']
    spec['Availability'] = 'drain'
    node.update(spec)
    
