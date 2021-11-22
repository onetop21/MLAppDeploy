from __future__ import annotations

import sys
import os
import re
import fnmatch
import uuid
import socket
import hashlib
import itertools
import jwt
from typing import Dict, Optional, TYPE_CHECKING
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlparse
from omegaconf import OmegaConf
from getpass import getuser

from mlad.cli.libs.exceptions import InvalidURLError

if TYPE_CHECKING:
    from mlad.cli.context import Context


HOME = str(Path.home())

CONFIG_PATH = f'{Path.home()}/.mlad'
CONFIG_FILE = f'{CONFIG_PATH}/config.yml'
COMPLETION_FILE = f'{CONFIG_PATH}/completion.sh'
PROJECT_FILE_ENV_KEY = 'MLAD_PRJFILE'
DEFAULT_PROJECT_FILE = 'mlad-project.yml'
DEFAULT_PLUGIN_FILE = 'mlad-plugin.yml'


def create_session_key():
    user = getuser()
    hostname = socket.gethostname()
    payload = {"user": user, "hostname": hostname, "uuid": str(uuid.uuid4())}
    encode = jwt.encode(payload, "mlad", algorithm="HS256")
    return encode


def get_workspace():
    '''
    Project Hash: [HOSTNAME]@[PROJECT DIR]
    '''
    key = f"{socket.gethostname()}:{get_project_file()}"
    return key


def workspace_key(workspace=None):
    if workspace is not None:
        return hash(workspace).hex
    return hash(get_workspace()).hex


def read_config():
    try:
        return OmegaConf.load(CONFIG_FILE)
    except FileNotFoundError:
        print('Need to initialize configuration before.\nTry to run "mlad config init"',
              file=sys.stderr)
        sys.exit(1)


def get_completion(shell='bash'):
    return os.popen(f"_MLAD_COMPLETE=source_{shell} mlad").read()


def write_completion(shell='bash'):
    with open(COMPLETION_FILE, 'wt') as f:
        f.write(get_completion(shell))
    if shell == 'bash':
        with open(f"{HOME}/.bash_completion", 'wt') as f:
            f.write(f". {COMPLETION_FILE}")


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
    path = project.get('workdir', './')
    if not os.path.isabs(path):
        project['workdir'] = os.path.normpath(
            os.path.join(
                os.path.dirname(project_file),
                path
            )
        )
    if not check_podname_syntax(project['name']):
        print('Syntax Error: Project and app require a name to '
              'follow standard as defined in RFC1123.', file=sys.stderr)
        sys.exit(1)

    return project


def print_table(data, no_data_msg=None, max_width=32, upper=True):
    if max_width > 0:
        widths = [max(_) for _ in zip(*[[min(len(str(value)), max_width) for value in datum]
                                        for datum in data])]
    else:
        widths = [max(_) for _ in zip(*[[len(str(value)) for value in datum] for datum in data])]
    format = '  '.join([('{:%d}' % _) for _ in widths])
    firstline = True
    for datum in data:
        datum = [_ if not isinstance(_, str) or len(_) <= w else f"{_[:w-3]}..."
                 for _, w in zip(datum, widths)]
        if firstline:
            if upper:
                print(format.format(*datum).upper())
            else:
                print(format.format(*datum))
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
    for _ in [_.ports[f'{internal_port}/tcp'] for _ in cli.containers.list()
              if _.name in [f'{container_name}']]:
        external_port = _[0]['HostPort']
    return external_port


def parse_url(url):
    try:
        parsed_url = urlparse(url)
        if not parsed_url.netloc:
            raise InvalidURLError
    except Exception:
        raise InvalidURLError
    return {
        'scheme': parsed_url.scheme or 'http',
        'username': parsed_url.username,
        'password': parsed_url.password,
        'hostname': parsed_url.hostname,
        'port': parsed_url.port or (443 if parsed_url.scheme == 'https' else 80),
        'path': parsed_url.path,
        'query': parsed_url.query,
        'params': parsed_url.params,
        'url': url if parsed_url.scheme else f"http://{url}",
        'address': url.replace(f"{parsed_url.scheme}://", "") if parsed_url.scheme else url
    }


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
            if fg % 10 == 1:
                # Remove Red Foreground
                continue
            if fg % 10 == bg % 10:
                continue
            color = ';'.join(['1', str(fg), str(bg)])
            table.append(f'\x1b[{color}m')
    return table


def color_index():
    global _color_counter
    if not hasattr(sys.modules[__name__], '_color_counter'):
        _color_counter = itertools.count()
    return next(_color_counter) % len(color_table())


def print_info(line):
    return f'{INFO_COLOR}{line}{CLEAR_COLOR}'


###############
def match(filepath, ignores):
    result = False
    normpath = os.path.normpath(filepath)
    
    def matcher(path, pattern):
        patterns = [pattern] + ([os.path.normpath(f"{pattern.replace('**/','/')}")]
                                if '**/' in pattern else [])
        result = map(lambda _: fnmatch.fnmatch(normpath, _) or
                     fnmatch.fnmatch(normpath, os.path.normpath(f"{_}/*")), patterns)
        return sum(result) > 0
    for ignore in ignores:
        if ignore.startswith('#'):
            pass
        elif ignore.startswith('!'):
            result &= not matcher(normpath, ignore[1:])
        else:
            result |= matcher(normpath, ignore)
    return result


def arcfiles(workspace='.', ignores=[]):
    ignores = [os.path.join(os.path.abspath(workspace), _)for _ in ignores]
    for root, dirs, files in os.walk(workspace):
        for name in files:
            filepath = os.path.join(root, name)
            if not match(filepath, ignores):
                yield filepath, os.path.relpath(os.path.abspath(filepath),
                                                os.path.abspath(workspace))
        prune_dirs = []
        for name in dirs:
            dirpath = os.path.join(root, name)
            if match(dirpath, ignores):
                prune_dirs.append(name)
        for _ in prune_dirs:
            dirs.remove(_)


def prompt(msg, default='', ty=str):
    return ty(input(f"{msg}:" if not default else f"{msg} [{default}]:")) or default


@lru_cache(maxsize=None)
def get_username(session):
    decoded = jwt.decode(session, "mlad", algorithms="HS256")
    if decoded["user"]:
        return decoded["user"]
    else:
        raise RuntimeError("Session key is invalid.")


# Process file option for cli
def process_file(file: Optional[str]):
    if file is not None and not os.path.isfile(file):
        raise FileNotFoundError('Project file is not exist.')
    file = file or os.environ.get(PROJECT_FILE_ENV_KEY, None)
    if file is not None:
        os.environ[PROJECT_FILE_ENV_KEY] = file


# Pasre log output for cli
def parse_log(log: Dict, max_name_width: int = 32, len_short_id: int = 20) -> str:
    name = log['name']
    name_width = min(max_name_width, log['name_width'])
    if 'task_id' in log:
        name = f'{name}.{log["task_id"][:len_short_id]}'
        name_width = min(max_name_width, name_width + len_short_id + 1)
    msg = log['stream'] if isinstance(log['stream'], str) else log['stream'].decode()
    timestamp = f'[{log["timestamp"]}]' if 'timestamp' in log else None
    if msg.startswith('Error'):
        return msg
    else:
        if timestamp is not None:
            return f'{timestamp} {name}: {msg}'
        else:
            return f'{name}: {msg}'


def get_registry_address(config: Context):
    parsed = parse_url(config.docker.registry.address)
    registry_address = parsed['address']
    namespace = config.docker.registry.namespace
    if namespace is not None:
        registry_address += f'/{namespace}'
    return registry_address