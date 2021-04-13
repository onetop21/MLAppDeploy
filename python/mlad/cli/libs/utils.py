import sys
import os
import re
import copy
import fnmatch
import uuid
import socket
import hashlib
import itertools
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlparse
from omegaconf import OmegaConf
from mlad.api import API
from mlad.api.exception import APIError, NotFoundError

HOME = str(Path.home())

CONFIG_PATH = HOME + '/.mlad'
CONFIG_FILE = CONFIG_PATH + '/config.yml'
COMPLETION_FILE = CONFIG_PATH + '/completion.sh'
PROJECT_FILE_ENV_KEY='MLAD_PRJFILE'
DEFAULT_PROJECT_FILE = 'mlad-project.yml'
DEFAULT_PLUGIN_FILE = 'mlad-plugin.yml'

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
    key = f"{socket.gethostname()}:{get_project_file()}"
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

#@lru_cache(maxsize=None)
def check_podname_syntax(obj):
    if isinstance(obj, dict):
        for _ in obj.keys():
            if not re.match('^([a-z]+[a-z0-9\-]*[a-z0-9]+|[a-z0-9])$', _):
                return False
    elif isinstance(obj, str):
        if not re.match('^([a-z]+[a-z0-9\-]*[a-z0-9]+|[a-z0-9])$', obj):
            return False
    else:
        return False
    return True

@lru_cache(maxsize=None)
def get_project_file():
    # Patch for WSL2 (/home/... -> /mnt/c/Users...)
    return os.path.realpath(os.environ.get('MLAD_PRJFILE', DEFAULT_PROJECT_FILE))

@lru_cache(maxsize=None)
def read_project():
    project_file = get_project_file()
    if os.path.isfile(project_file):
        project = OmegaConf.to_container(OmegaConf.load(project_file), resolve=True)
        return project
    else:
        return None

@lru_cache(maxsize=None)
def get_project(default_project):
    project = read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print(f'$ {sys.argv[0]} --help', file=sys.stderr)
        sys.exit(1)

    # replace workdir to abspath
    project_file = get_project_file()
    project = default_project(project)
    path = project['project'].get('workdir', './')
    if not os.path.isabs(path):
        project['project']['workdir'] = os.path.normpath(
            os.path.join(
                os.path.dirname(project_file),
                path
            )
        )
    if not check_podname_syntax(project['project']['name']) or not check_podname_syntax(project['services']):
        print('Syntax Error: Project(Plugin) and service require a name to follow standard as defined in RFC1123.', file=sys.stderr)
        sys.exit(1)
    return project

@lru_cache(maxsize=None)
def manifest_file(ty='project'):
    # Patch for WSL2 (/home/... -> /mnt/c/Users...)
    if ty == 'project':
        return os.path.realpath(os.environ.get('MLAD_PRJFILE', DEFAULT_PROJECT_FILE))
    elif ty == 'plugin':
        return os.path.realpath(DEFAULT_PLUGIN_FILE)

@lru_cache(maxsize=None)
def read_manifest(path):
    if os.path.isfile(path):
        manifest = OmegaConf.to_container(OmegaConf.load(path), resolve=True)
        return manifest
    else:
        return None

@lru_cache(maxsize=None)
def get_manifest(ty, default=lambda x: x):
    manifest_path = manifest_file(ty)
    manifest = read_manifest(manifest_path)
    if not manifest:
        print(f'Need to generate {ty} manifest file before.', file=sys.stderr)
        print(f'$ {sys.argv[0]} --help', file=sys.stderr)
        sys.exit(1)

    # replace workdir to abspath
    manifest = default(manifest)
    path = manifest[ty].get('workdir', './')
    if not os.path.isabs(path):
        manifest[ty]['workdir'] = os.path.normpath(
            os.path.join(
                os.path.dirname(manifest_path),
                path
            )
        )
    if not check_podname_syntax(manifest[ty]['name']):
        print('Syntax Error: Project(Plugin) and service require a name to follow standard as defined in RFC1123.', file=sys.stderr)
        sys.exit(1)
    return manifest

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

@lru_cache(maxsize=None)
def get_advertise_addr():
    # If this local machine is WSL2
    if 'microsoft' in os.uname().release:
        print("Wait for getting host IP address...")
        import subprocess
        output = subprocess.check_output(['powershell.exe', '-Command', '(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -ne "Disconnected" }).IPv4Address.IPAddress'])
        addr = output.strip(b'\r\n').decode()
        sys.stdout.write("\033[1A\033[K")
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

def parse_url(url):
    parsed_url = urlparse(url)
    return {
        'scheme':   parsed_url.scheme or 'http',
        'username': parsed_url.username,
        'password': parsed_url.password,
        'hostname': parsed_url.hostname,
        'port':     parsed_url.port or (443 if parsed_url.scheme == 'https' else 80),
        'path':     parsed_url.path,
        'query':    parsed_url.query,
        'params':   parsed_url.params,
        'url':      url if parsed_url.scheme else f"http://{url}",
        'address':  url.replace(f"{parsed_url.scheme}://","") if parsed_url.scheme else url
    }

def get_service_env(config):
    env = [
        f'MLAD_ADDRESS={config["mlad"]["address"]}',
        f'MLAD_USER_TOKEN={config["mlad"]["token"]["user"]}',
    ]
    return env

def generate_unique_id(length=None):
    UUID = uuid.uuid4()
    if length:
        return UUID.hex[:length]
    else:
        return UUID

def hash(body: str):
    return uuid.UUID(hashlib.md5(body.encode()).hexdigest())

# for Log Coloring
CLEAR_COLOR = '\x1b[0m'
ERROR_COLOR = '\x1b[1;31;40m'
INFO_COLOR = '\033[38;2;255;140;26m'


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

def prompt(msg, default='', ty=str):
    return ty(input(f"{msg}:" if not default else f"{msg} [{default}]:")) or default
    
@lru_cache(maxsize=None)
def get_username(config):
    with API(config.mlad.address, config.mlad.token.user) as api:
        res = api.auth.token_verify()
    if res['result']:
        return res['data']['username']
    else:
        raise RuntimeError("Token is not valid.")



