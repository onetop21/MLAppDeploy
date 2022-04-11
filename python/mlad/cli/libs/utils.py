from __future__ import annotations

import sys
import os
import uuid
import socket
import hashlib
import itertools
import subprocess

import jwt
import yaml

from typing import Dict, Optional, List, Any
from functools import lru_cache
from datetime import datetime
from dateutil import parser

from yaml.parser import ParserError
from mlad.cli.exceptions import ProjectLoadError
from mlad.core.libs.constants import (
    MLAD_PROJECT, MLAD_PROJECT_WORKSPACE, MLAD_PROJECT_USERNAME,
    MLAD_PROJECT_API_VERSION, MLAD_PROJECT_NAME, MLAD_PROJECT_MAINTAINER,
    MLAD_PROJECT_VERSION, MLAD_PROJECT_BASE, MLAD_PROJECT_IMAGE, MLAD_PROJECT_SESSION,
    MLAD_PROJECT_KIND, MLAD_PROJECT_NAMESPACE, MLAD_PROJECT_ENV
)
from mlad.core.libs import utils as core_utils

PROJECT_FILE_ENV_KEY = 'MLAD_PRJFILE'
DEFAULT_PROJECT_FILE = 'mlad-project.yml'


def get_workspace():
    '''
    Project Hash: [HOSTNAME]@[PROJECT DIR]
    '''
    key = f"{socket.gethostname()}:{get_project_file()}"
    return key


def workspace_key(workspace=None):

    def _hash(body: str):
        return uuid.UUID(hashlib.md5(body.encode()).hexdigest())

    if workspace is not None:
        return _hash(workspace).hex
    return _hash(get_workspace()).hex


@lru_cache(maxsize=None)
def obtain_my_ip():
    if 'microsoft' in os.uname().release:
        output = subprocess.check_output([
            'powershell.exe',
            '-Command',
            ('(Get-NetIPConfiguration | '
             'Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -ne "Disconnected" }).IPv4Address.IPAddress')
        ])
        ip = output.strip(b'\r\n').decode()
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
    return ip


def get_project_file():
    # Patch for WSL2 (/home/... -> /mnt/c/Users...)
    return os.path.realpath(os.environ.get('MLAD_PRJFILE', DEFAULT_PROJECT_FILE))


def read_project():
    project_file_path = get_project_file()
    if os.path.isfile(project_file_path):
        with open(project_file_path, 'r') as project_file:
            try:
                return yaml.load(project_file, Loader=yaml.FullLoader)
            except ParserError as e:
                raise ProjectLoadError(str(e))
    else:
        return None


def get_project():
    project = read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print(f'$ {sys.argv[0]} --help', file=sys.stderr)
        sys.exit(1)

    # validate project schema
    from mlad.cli.validator import validators
    project = validators.validate(project)

    # replace workdir to abspath
    project_file = get_project_file()
    path = project.get('workdir', './')
    if not os.path.isabs(path):
        project['workdir'] = os.path.normpath(
            os.path.join(
                os.path.dirname(project_file),
                path
            )
        )
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
        datum = ['None' if _ is None else _ for _ in datum]
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


# for Log Coloring
CLEAR_COLOR = '\x1b[0m'
ERROR_COLOR = '\x1b[1;31;40m'
INFO_COLOR = '\033[38;2;255;140;26m'
OK_COLOR = '\033[92m'


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


def info_msg(line):
    return f'{INFO_COLOR}{line}{CLEAR_COLOR}'


def prompt(msg, default='', ty=str):
    return ty(input(f"{msg}:" if not default else f"{msg} [{default}]:")) or default


@lru_cache(maxsize=None)
def get_username(session):
    decoded = jwt.decode(session, "mlad", algorithms="HS256")
    if decoded["user"]:
        return decoded["user"]
    else:
        raise RuntimeError("Session key is invalid.")


# Manage Project and Namespace
def base_labels(workspace: str, session: str, project: Dict, extra_envs: List[str],
                registry_address: str, build: bool = False):
    # workspace = f"{hostname}:{workspace}"
    # Server Side Config 에서 가져올 수 있는건 직접 가져온다.
    username = get_username(session)
    key = workspace_key(workspace=workspace)
    kind = project['kind']
    version = str(project['version']).lower()
    repository = f"{username}/{project['name']}-{key[:10]}:{version}".lower()
    if kind == 'Deployment':
        repository = f'{registry_address}/' + repository
    basename = f"{username}-{project['name']}-{key[:10]}".lower()

    labels = {
        MLAD_PROJECT: key,
        MLAD_PROJECT_WORKSPACE: workspace,
        MLAD_PROJECT_USERNAME: username,
        MLAD_PROJECT_API_VERSION: project['apiVersion'],
        MLAD_PROJECT_NAME: project['name'].lower(),
        MLAD_PROJECT_MAINTAINER: project['maintainer'],
        MLAD_PROJECT_VERSION: str(project['version']).lower(),
        MLAD_PROJECT_BASE: basename,
        MLAD_PROJECT_NAMESPACE: f'{basename}-cluster',
        MLAD_PROJECT_ENV: core_utils.encode_dict(extra_envs),
        MLAD_PROJECT_IMAGE: repository,
        MLAD_PROJECT_SESSION: session,
        MLAD_PROJECT_KIND: project['kind']
    }
    return labels


# Process file option for cli
def process_file(file: Optional[str]):
    if file is not None and not os.path.isfile(file):
        raise FileNotFoundError('Project file is not exist.')
    file = file or os.environ.get(PROJECT_FILE_ENV_KEY, None)
    if file is not None:
        os.environ[PROJECT_FILE_ENV_KEY] = file


def created_to_age(created: str):
    # param created: str of datetime
    uptime = (datetime.utcnow() - parser.parse(created).replace(tzinfo=None)).total_seconds()
    if uptime > 24 * 60 * 60:
        uptime = f"{uptime // (24 * 60 * 60):.0f} days"
    elif uptime > 60 * 60:
        uptime = f"{uptime // (60 * 60):.0f} hours"
    elif uptime > 60:
        uptime = f"{uptime // 60:.0f} minutes"
    else:
        uptime = f"{uptime:.0f} seconds"
    return uptime


def _k8s_object_to_dict(obj: Any) -> Dict:
    ret = {}
    attribute_map = obj.attribute_map
    for openapi_type in obj.openapi_types:
        value = getattr(obj, openapi_type)
        if value is None:
            continue
        if isinstance(value, list):
            ret[attribute_map[openapi_type]] = list(map(
                lambda x: _k8s_object_to_dict(x) if hasattr(x, 'to_dict') else x,
                value
            ))
        elif hasattr(value, 'to_dict'):
            ret[attribute_map[openapi_type]] = _k8s_object_to_dict(value)
        elif isinstance(value, dict):
            ret[attribute_map[openapi_type]] = dict(map(
                lambda item: (item[0], _k8s_object_to_dict(item[1]))
                if hasattr(item[1], 'to_dict') else item,
                value.items()
            ))
        else:
            ret[attribute_map[openapi_type]] = value
    return ret


def dump_k8s_object_to_yaml(path: str, objs: List[Any]):
    dicts = [_k8s_object_to_dict(obj) for obj in objs]
    with open(path, 'w') as yaml_file:
        yaml.dump_all(dicts, yaml_file, default_flow_style=False, sort_keys=False)
