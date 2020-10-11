import sys, os, copy 
from pathlib import Path
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError as e:
    from yaml import Loader, Dumper

HOME = str(Path.home())
CONFIG_PATH = HOME + '/.mlad'
CONFIG_FILE = HOME + '/.mlad/config.yml'
PROJECT_PATH = os.getcwd()
PROJECT_FILE = os.getcwd() + '/mlad-project.yml'

ProjectArgs = {
    'project_file': PROJECT_FILE,
    'working_dir': PROJECT_PATH
}

def apply_project_arguments(project_file=None, workdir=None):
    if project_file: ProjectArgs['project_file'] = project_file
    if workdir:
        ProjectArgs['working_dir'] = workdir
    else:
        ProjectArgs['working_dir'] = os.path.dirname(ProjectArgs['project_file'])

def getProjectFile():
    return ProjectArgs['project_file']

def getWorkingDir():
    return ProjectArgs['working_dir']

def generate_empty_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_PATH, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write('')

def getProjectConfigPath(project):
    config = read_config()
    return '%s/%s/%s'%(CONFIG_PATH, config['account']['username'], project['name'].lower())

def getProjectName(project):
    config = read_config()
    return '{USERNAME}_{PROJECT}'.format(USERNAME=config['account']['username'], PROJECT=project['name'].lower())

def getRepository(project):
    config = read_config()
    if 'registry' in config['docker']:
        repository = f"{config['docker']['registry']}/{config['account']['username']}/{project['name'].lower()}"
    else:
        repository = f"{config['account']['username']}/{project['name'].lower()}"
    return repository

def read_config():
    try:
        with open(CONFIG_FILE) as f:
            config = load(f.read(), Loader=Loader)
        return config or {}
    except FileNotFoundError as e:
        print('Need to initialize configuration before.\nTry to run "mlad config init"', file=sys.stderr)
        sys.exit(1)

def write_config(config):
    with open(CONFIG_FILE, 'w') as f:
        f.write(dump(config, default_flow_style=False, Dumper=Dumper))

def read_project():
    if os.path.exists(getProjectFile()):
        with open(getProjectFile()) as f:
            project = load(f.read(), Loader=Loader)
        return project or {}
    else:
        return None

def get_project(default_project):
    project = read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    return default_project(project)

def print_table(data, no_data_msg=None, max_width=32):
    widths = [max(_) for _ in zip(*[[min(len(str(value)), max_width) for value in datum] for datum in data])]
    format = '  '.join([('{:%d}' % _) for _ in widths])
    titled = False
    for datum in data:
        if not titled:
            print(format.format(*datum).upper())
            titled = True
        else:
            print(format.format(*datum))
    if len(data) < 2:
        print(no_data_msg, file=sys.stderr)

def convert_dockerfile(project, workspace):
    config = read_config()
    from mladcli.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT

    envs = [
        #DOCKERFILE_ENV.format(KEY='TF_CPP_MIN_LOG_LEVEL', VALUE=3),
        #DOCKERFILE_ENV.format(KEY='S3_ENDPOINT', VALUE=config['s3']['endpoint']),
        #DOCKERFILE_ENV.format(KEY='S3_USE_HTTPS', VALUE=0),
        #DOCKERFILE_ENV.format(KEY='AWS_ACCESS_KEY_ID', VALUE=config['s3']['accesskey']),
        #DOCKERFILE_ENV.format(KEY='AWS_SECRET_ACCESS_KEY', VALUE=config['s3']['secretkey']),
    ]
    for key in workspace['env'].keys():
        envs.append(DOCKERFILE_ENV.format(
            KEY=key,
            VALUE=workspace['env'][key]
        ))
    requires = []
    for key in workspace['requires'].keys():
        if key == 'apt':
            requires.append(DOCKERFILE_REQ_APT.format(
                SRC=workspace['requires'][key]
            ))
        elif key == 'pip':
            requires.append(DOCKERFILE_REQ_PIP.format(
                SRC=workspace['requires'][key]
            )) 

    PROJECT_CONFIG_PATH = getProjectConfigPath(project)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'

    os.makedirs(PROJECT_CONFIG_PATH, exist_ok=True)
    with open(DOCKERFILE_FILE, 'w') as f:
        f.write(DOCKERFILE.format(
            BASE=workspace['base'],
            AUTHOR=project['author'],
            ENVS='\n'.join(envs),
            PRESCRIPTS=';'.join(workspace['prescripts']) if len(workspace['prescripts']) else "echo .",
            REQUIRES='\n'.join(requires),
            POSTSCRIPTS=';'.join(workspace['postscripts']) if len(workspace['postscripts']) else "echo .",
            COMMAND='[%s]'%', '.join(
                ['"{}"'.format(item) for item in workspace['command'].split()] + 
                ['"{}"'.format(item) for item in workspace['arguments'].split()]
            ),
        ))

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

def get_advertise_addr():
    # If this local machine is WSL2
    if 'microsoft' in os.uname().release:
        print("Wait for getting host IP address...")
        import subprocess
        output = subprocess.check_output(['powershell.exe', '-Command', '(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -ne "Disconnected" }).IPv4Address.IPAddress'])
        addr = output.strip(b'\r\n').decode()
    else:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        addr = s.getsockname()[0]
        s.close()
    return addr

def is_host_wsl2(docker_host=None):
    # Check WSL2 in Docker Host, Not Local Machine!
    import docker
    if not docker_host:
        config = read_config()
        docker_host = config['docker']['host']
    cli = docker.from_env(environment={ 'DOCKER_HOST': docker_host })
    return 'microsoft' in cli.info()['KernelVersion']

def get_default_service_port(container_name, internal_port, docker_host=None):
    import docker
    if not docker_host:
        config = read_config()
        docker_host = config['docker']['host']
    cli = docker.from_env(environment={ 'DOCKER_HOST': docker_host })
    external_port = None
    for _ in [_.ports[f'{internal_port}/tcp'] for _ in cli.containers.list() if _.name in [f'{container_name}']]: 
        external_port = _[0]['HostPort']
    return external_port

def get_service_env():
    config = read_config()
    env = [
        f'S3_ENDPOINT={config["s3"]["endpoint"]}',
        f'S3_USE_HTTPS={1 if config["s3"]["verify"] else 0}',
        f'AWS_ACCESS_KEY_ID={config["s3"]["accesskey"]}',
        f'AWS_SECRET_ACCESS_KEY={config["s3"]["secretkey"]}',
    ]
    return env
