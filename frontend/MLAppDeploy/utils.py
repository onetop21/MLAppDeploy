import sys, os, copy, time, datetime
from pathlib import Path
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError as e:
    from yaml import Loader, Dumper
import docker

HOME = str(Path.home())
CONFIG_PATH = HOME + '/.mlad'
CONFIG_FILE = HOME + '/.mlad/config.yml'
PROJECT_PATH = os.getcwd()
PROJECT_FILE = os.getcwd() + '/mlad-project.yml'

def generate_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_PATH, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write('')

def read_config():
    with open(CONFIG_FILE) as f:
        config = load(f.read(), Loader=Loader)
    return config or {}

def write_config(config):
    with open(CONFIG_FILE, 'w') as f:
        f.write(dump(config, default_flow_style=False, Dumper=Dumper))

def read_project():
    if os.path.exists(PROJECT_FILE):
        with open(PROJECT_FILE) as f:
            project = load(f.read(), Loader=Loader)
        return project or {}
    else:
        return None

def convert_dockerfile(project, workspace):
    from MLAppDeploy.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_DEPEND_PIP, DOCKERFILE_DEPEND_APT
    project_name = project['name'].lower()

    envs = []
    for key in workspace['env'].keys():
        envs.append(DOCKERFILE_ENV.format(
            KEY=key,
            VALUE=workspace['env'][key]
        ))
    depends = []
    for key in workspace['depends'].keys():
        if key == 'apt':
            depends.append(DOCKERFILE_DEPEND_APT.format(
                SRC=workspace['depends'][key]
            ))
        elif key == 'pip':
            depends.append(DOCKERFILE_DEPEND_PIP.format(
                SRC=workspace['depends'][key]
            )) 

    PROJECT_CONFIG_PATH = '%s/%s'%(CONFIG_PATH, project_name)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'

    os.makedirs(PROJECT_CONFIG_PATH, exist_ok=True)
    with open(DOCKERFILE_FILE, 'w') as f:
        f.write(DOCKERFILE.format(
            BASE=workspace['base'],
            AUTHOR=project['author'],
            ENVS='\n'.join(envs),
            DEPENDS='\n'.join(depends),
            ENTRYPOINT=', '.join(workspace['entrypoint'].split()),
            ARGS=', '.join(workspace['arguments'].split()),
        ))

def generate_image(project, workspace, is_test=False):
    config = read_config()
    project_name = project['name'].lower()
    project_version=project['version'].lower()
    image_name = ('{REPO}/{OWNER}/{NAME}:{VER}_{TIMESTAMP}' + '-test' if is_test else '').format(
        REPO=config['registry'],
        OWNER=config['username'],
        NAME=project_name,
        VER=project_version,
        TIMESTAMP=datetime.datetime.now().strftime('%y%m%d.%H%M%S')
    )

    PROJECT_CONFIG_PATH = '%s/%s'%(CONFIG_PATH, project_name)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'
    DOCKERIGNORE_FILE = PROJECT_PATH + '/.dockerignore'

    # Generate dockerignore
    with open(DOCKERIGNORE_FILE, 'w') as f:
        f.write('\n'.join(workspace['ignore']))

    # Docker build
    cli = docker.from_env()
    cli.images.build(
        path=PROJECT_PATH,
        tag=image_name,
        dockerfile=DOCKERFILE_FILE
    )

    # Remove dockerignore
    os.unlink(DOCKERIGNORE_FILE)

    return project_name, image_name

def publish_image(project, services, is_test=False):
    #docker.image    
    pass
    
def create_services(project_name, image_name, services, local=False):
    import MLAppDeploy.default as default

    config = read_config()

    wait_queue = list(services.keys())
    running_queue = []

    cli = docker.from_env()

    # Create Docker Network
    networks = [ 
        '%s_backend' % (project_name),
    ]
    for network in networks:
        try:
            cli.networks.create(network, driver='overlay', ingress='frontend' in network)
        except docker.errors.APIError as e:
            print(e, file=sys.stderr)
            sys.exit(1)

    # Create Docker Service
    instances = []
    while len(wait_queue):
        service_key = wait_queue.pop(0)
        service = default.project_service(services[service_key])

        print(service_key, service['depends'], wait_queue)

        requeued = False
        for depend in service['depends']:
            if not depend in running_queue:
                wait_queue.append(service_key)
                requeued = True
                break
        if not requeued:
            service_name = service_key.lower()
            image = service['image'] or image_name
            env = [ '{KEY}={VALUE}'.format(KEY=key, VALUE=service['env'][key]) for key in service['env'].keys() ]
            args = service['arguments']
            labels = {'MLAD.PROJECT': project_name}
            
            restart_policy = docker.types.RestartPolicy()
            resources = docker.types.Resources()
            service_mode = docker.types.ServiceMode('replicated')
            constraints = []
            if not local:
                resources = docker.types.Resources(
                    cpu_limit=service['deploy']['quotes']['cpu'],
                    cpu_reservation=service['deploy']['quotes']['cpu'],
                    generic_resources={ 'gpu': service['deploy']['qoutes']['gpu'] }
                )
                service_mode = docker.types.ServiceMode('replicated', replicas=service['deploy']['replicas'])
                constraints = [ '{KEY}={VALUE}'.format(KEY=key, VALUE=service['deploy']['constraints'][key]) for key in service['deploy']['constraints'] ]

            instance = cli.services.create(
                name='{PROJECT}_{SERVICE}'.format(PROJECT=project_name, SERVICE=service_name),
                image=image, 
                env=env,
                command=args,
                container_labels=labels,
                labels=labels,
                networks = networks,
                restart_policy=restart_policy,
                resources=resources,
                mode=service_mode,
                constraints=constraints
            )
            instances.append(instance)
            running_queue.append(service_key)
        #for inst in instances:
        #    print(inst.tasks())
        time.sleep(1)
            
def merge(source, destination):
    if source:
        for key, value in source.items():
            if isinstance(value, dict):
                # get node or create one
                node = destination.setdefault(key, {})
                merge(value, node)
            else:
                destination[key] = value
    return destination 

def update_obj(base, obj):
    # Remove no child branch
    que=[obj]
    while len(que):
        item = que.pop(0)
        if isinstance(item, dict):
            removal_keys = []
            for key in item.keys():
                if key != 'services':
                    if not item[key] is None:
                        que.append(item[key])
                    else:
                        removal_keys.append(key)
            for key in removal_keys:
                del item[key]
    return merge(obj, copy.deepcopy(base))

