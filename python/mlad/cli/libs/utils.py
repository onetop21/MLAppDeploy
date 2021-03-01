import sys
import os
import copy
import fnmatch
import uuid
import socket
from pathlib import Path
from omegaconf import OmegaConf

HOME = str(Path.home())

CLIENT_CONFIG_PATH = HOME + '/.mlad'
SERVICE_CONFIG_PATH = '/opt/mlad'
CONFIG_PATH = CLIENT_CONFIG_PATH

CLIENT_CONFIG_FILE = CLIENT_CONFIG_PATH + '/config.yml'
SERVICE_CONFIG_FILE = SERVICE_CONFIG_PATH + '/config.yml'
CONFIG_FILE = CLIENT_CONFIG_FILE
COMPLETION_FILE = CLIENT_CONFIG_FILE + '/completion.sh'
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
        ProjectArgs['working_dir'] = os.path.dirname(ProjectArgs['project_file']) or '.'

def get_project_file():
    return ProjectArgs['project_file']

def get_working_dir():
    return ProjectArgs['working_dir']

def generate_empty_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_PATH, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write('')

def get_workspace():
    '''
    Project Hash: [HOSTNAME]@[PROJECT DIR]
    '''
    key = f"{socket.gethostname()}:{ProjectArgs['project_file']}"
    return key

def project_key(workspace):
    return hash(workspace).hex

def has_config():
    return os.path.exists(CONFIG_FILE)

def read_config():
    try:
        return OmegaConf.load(CONFIG_FILE)
    except FileNotFoundError as e:
        print('Need to initialize configuration before.\nTry to run "mlad config init"', file=sys.stderr)
        sys.exit(1)

def write_config(config):
    OmegaConf.save(config=config, f=CONFIG_FILE)

def get_completion(shell='bash'):
    return os.popen(f"_MLAD_COMPLETE=source_{shell} mlad").read()

def write_completion(shell='bash'):
    with open(COMPLETION_FILE, 'wt') as f:
        f.write(get_completion(shell))
    if shell == 'bash':
        with open(f"{HOME}/.bash_completion", 'wt') as f:
            f.write(f". {COMPLETION_FILE}")

def read_project():
    if os.path.exists(get_project_file()):
        try:
            project = OmegaConf.to_container(OmegaConf.load(get_project_file()), resolve=True)
        except FileNotFoundError:
            project = {}
        return project
    else:
        return None

def get_project(default_project):
    project = read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print(f'$ {sys.argv[0]} --help', file=sys.stderr)
        sys.exit(1)

    return default_project(project)

def print_table(data, no_data_msg=None, max_width=32):
    if max_width > 0:
        widths = [max(_) for _ in zip(*[[min(len(str(value)), max_width) for value in datum] for datum in data])]
    else:
        widths = [max(_) for _ in zip(*[[len(str(value)) for value in datum] for datum in data])]
    format = '  '.join([('{:%d}' % _) for _ in widths])
    firstline = True
    for datum in data:
        datum = [_ if not isinstance(_, str) or len(_) <= w else f"{_[:w-3]}..." for _, w in zip(datum, widths)]
        if firstline:
            print(format.format(*datum).upper())
            firstline = False
        else:
            print(format.format(*datum))
    if len(data) < 2:
        print(no_data_msg, file=sys.stderr)

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

def get_default_service_port(container_name, internal_port):
    import docker
    cli = docker.from_env()
    external_port = None
    for _ in [_.ports[f'{internal_port}/tcp'] for _ in cli.containers.list() if _.name in [f'{container_name}']]: 
        external_port = _[0]['HostPort']
    return external_port

def get_service_env(config):
    env = [
        f'S3_ENDPOINT={config["environment"]["s3"]["endpoint"]}',
        f'S3_USE_HTTPS={1 if config["environment"]["s3"]["verify"] else 0}',
        f'AWS_ACCESS_KEY_ID={config["environment"]["s3"]["accesskey"]}',
        f'AWS_SECRET_ACCESS_KEY={config["environment"]["s3"]["secretkey"]}',
    ]
    return env

def generate_unique_id(length=None):
    UUID = uuid.uuid4()
    if length:
        return UUID.hex[:length]
    else:
        return UUID

def hash(body: str):
    import hashlib
    return uuid.UUID(hashlib.md5(body.encode()).hexdigest())

# for Log Coloring
CLEAR_COLOR = '\x1b[0m'
ERROR_COLOR = '\x1b[1;31;40m'

import itertools
from functools import lru_cache
@lru_cache(maxsize=None)
def color_table():
    table = []
    for bg in range(40, 48):
        for fg in range(30, 38):
            if fg % 10 == 1: continue # Remove Red Foreground
            if fg % 10 == bg % 10: continue
            color = ';'.join(['1', str(fg), str(bg)])
            table.append(f'\x1b[{color}m')
    return table

def color_index():
    global _color_counter
    if not hasattr(sys.modules[__name__], '_color_counter'): _color_counter = itertools.count()
    return next(_color_counter) % len(color_table())

###############
def match(filepath, ignores):
    result = False
    normpath = os.path.normpath(filepath)
    for ignore in ignores:
        if ignore.startswith('#'):
            pass
        elif ignore.startswith('!'):
            result &= not fnmatch.fnmatch(normpath, ignore[1:])
        else:
            result |= fnmatch.fnmatch(normpath, ignore)
    return result

def arcfiles(workspace='.', ignores=[]):
    for root, dirs, files in os.walk(workspace):
        for name in files:
            filepath = os.path.join(root, name)
            if not match(filepath, ignores):
                yield filepath, os.path.relpath(os.path.abspath(filepath), os.path.abspath(workspace))
        prune_dirs = []
        for name in dirs:
            dirpath = os.path.join(root, name)
            if match(dirpath, ignores):
                prune_dirs.append(name)
        for _ in prune_dirs: dirs.remove(_)

def to_url(dic):
    scheme = 'http://'
    if dic['port']:
        return f"{scheme}{dic['host']}:{dic['port']}"
    else:
        return f"{scheme}{dic['host']}"

def prompt(msg, default=None, ty=str):
    return ty(input(f"{msg}:" if not default else f"{msg} [{default}]:")) or default
    
