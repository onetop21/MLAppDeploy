import os
import errno
import time
import re
import yaml
import docker
import requests
from requests.exceptions import ConnectionError

from docker.types import Mount
from typing import List
from mlad.cli import config as config_core
from mlad.cli.exceptions import (
    MLADBoardNotActivatedError, ComponentImageNotExistError,
    MLADBoardAlreadyActivatedError, CannotBuildComponentError
)
from mlad.cli import image as image_core
from mlad.cli.libs import utils
from mlad.core.docker.controller import get_cli


class ValueGenerator:
    def __init__(self, generator):
        self.gen = generator

    def __iter__(self):
        self.value = yield from self.gen

    def get_value(self):
        for x in self:
            pass
        return self.value


def activate(image_repository: str):
    cli = get_cli()
    config = config_core.get()

    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        pass
    else:
        raise MLADBoardAlreadyActivatedError

    try:
        host_ip = _obtain_host()
        requests.delete(f'{host_ip}:2021/mlad/component', json={
            'name': 'mlad-board'
        })
    except ConnectionError:
        pass

    yield 'Activating MLAD board.'

    # if image tag is dev version, change to latest
    group = re.match(r'([a-z0-9.:-]+/[a-z0-9./-]+)(?P<OFFICIAL>:[0-9.]+$)?(?P<DEV>:[a-z0-9.]+$)?', image_repository)
    if group.group('DEV'):
        image_repository = f"{group.group(1)}:latest"

    cli.containers.run(
        image_repository,
        environment=[
            f'MLAD_ADDRESS={config_core.obtain_server_address(config)}',
            f'MLAD_SESSION={config["session"]}',
        ] + config_core.get_env(),
        name='mlad-board',
        ports={'2021/tcp': '2021'},
        labels=['MLAD_BOARD'],
        detach=True,
        restart_policy={'Name': 'always'}
    )

    host_ip = _obtain_host()
    yield 'Successfully activate MLAD board.'
    yield f'MLAD board is running at {host_ip}:2021.'


def deactivate():
    cli = get_cli()
    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        raise MLADBoardNotActivatedError

    yield 'Deactivating MLAD board.'

    try:
        host_ip = _obtain_host()
        requests.delete(f'{host_ip}:2021/mlad/component', json={
            'name': 'mlad-board'
        })
    except ConnectionError:
        pass

    containers = cli.containers.list(filters={
        'label': 'MLAD_BOARD'
    }, all=True)
    for container in containers:
        container.stop()
        container.remove()

    yield 'Successfully deactivate MLAD board.'


def install(file_path: str, no_build: bool):
    cli = get_cli()
    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        raise MLADBoardNotActivatedError

    yield f'Read the component spec from {file_path or "./mlad-project.yml"}.'

    try:
        with open(file_path, 'r') as component_file:
            spec = yaml.load(component_file)
    except Exception:
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file_path)

    from mlad.cli.validator import validators
    spec = validators.validate(spec)
    if not no_build and 'workspace' not in spec:
        no_build = True

    labels = {
        'MLAD_BOARD': '',
        'COMPONENT_NAME': spec['name']
    }
    if no_build:
        built_images = cli.images.list(filters={'label': labels})
        if len(built_images) > 0:
            image = built_images[0]
        else:
            image = None
    else:
        image = ValueGenerator(image_core.build(file_path, False, True, False)).get_value()

    host_ip = _obtain_host()
    component_specs = []
    for app_name, component in spec['app'].items():
        if 'image' in component:
            image_name = component['image']
            cli.images.pull(image_name)
            image = cli.images.get(image_name)
        elif image is None:
            raise ComponentImageNotExistError(spec['name'])
        env = {**component.get('env', dict()), **config_core.get_env(dict=True)}
        ports = [expose['port'] for expose in component.get('expose', [])]
        hidden = {expose['port']: expose['hidden'] for expose in component.get('expose', [])}
        command = component.get('command', [])
        if isinstance(command, str):
            command = command.split(' ')
        args = component.get('args', [])
        if isinstance(args, str):
            args = args.split(' ')
        mounts = component.get('mounts', [])
        labels = {
            'MLAD_BOARD': '',
            'COMPONENT_NAME': spec['name'],
            'APP_NAME': app_name
        }
        yield f'Run the container [{app_name}]'
        # patch env vars
        schema = re.match(r'http[s]?://([^/]+)', host_ip)
        parsed = config_core._parse_url(host_ip)
        env = {'HOST_IP': parsed['address'], **env, **{k: (env.get(v[1:]) if v.startswith('$') else v) for k, v in env.items()}}
        command = [env.get(_[1:]) if _.startswith('$') else _ for _ in command]
        ################
        container = cli.containers.run(
            image.tags[-1],
            environment=env,
            name=f'{spec["name"]}-{app_name}',
            #ports={f'{p}/tcp': p for p in ports},
            ports={f'{p}/tcp': None for p in ports},
            command=command + args,
            mounts=[Mount(source=mount['path'], target=mount['mountPath'], type='bind')
                    for mount in mounts],
            labels=labels,
            detach=True,
            restart_policy={'Name': 'always'}
        )
        # Wait for getting port
        for _ in range(10):
            container.reload()
            port_bindings = container.attrs['NetworkSettings']['Ports']
            should_wait = False
            for p in ports:
                target_ports = port_bindings[f'{p}/tcp']
                should_wait |= len(target_ports) == 0 or 'HostPort' not in target_ports[0]
            if not should_wait:
                break
            time.sleep(1)
        #######################
        if port_bindings:
            component_specs.append({
                'name': spec['name'],
                'app_name': app_name,
                #'hosts': [f'{host_ip}:{p}' for p in ports]
                'hosts': [f'{host_ip}:{port_bindings[f"{p}/tcp"][0]["HostPort"]}' for p in ports if hidden[p] is not True]
            })

            res = requests.post(f'{host_ip}:2021/mlad/component', json={
                'components': component_specs
            })
            res.raise_for_status()

    yield 'The component installation is complete.'


def uninstall(name: str) -> None:
    cli = get_cli()
    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        raise MLADBoardNotActivatedError

    host_ip = _obtain_host()
    res = requests.delete(f'{host_ip}:2021/mlad/component', json={
        'name': name
    })
    res.raise_for_status()

    containers = cli.containers.list(filters={
        'label': f'COMPONENT_NAME={name}'
    }, all=True)
    for container in containers:
        container.stop()

    for container in containers:
        container.remove()

    yield f'The component [{name}] is uninstalled'


def status(no_print: bool = False):
    cli = get_cli()
    is_board_active = True

    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        is_board_active = False

    yield f'MLAD board is [{"active" if is_board_active else "inactive"}].'

    containers = cli.containers.list(filters={
        'label': 'MLAD_BOARD'
    }, all=True)
    containers = [c for c in containers if c.name != 'mlad-board']
    ports_list = [_obtain_ports(c) for c in containers]
    columns = [('ID', 'NAME', 'APP_NAME', 'PORT')]
    for container, ports in zip(containers, ports_list):
        if len(ports) == 0:
            ports = ['-']
        for port in ports:
            columns.append((
                container.short_id,
                container.labels['COMPONENT_NAME'],
                container.labels['APP_NAME'],
                port
            ))
    if not no_print:
        utils.print_table(columns, 'No components installed', 0)
    return containers


def _obtain_host():
    return f'http://{utils.obtain_my_ip()}'


def _obtain_ports(container) -> List[str]:
    lo_cli = get_cli().api
    port_data = lo_cli.inspect_container(container.id)['NetworkSettings']['Ports']
    return [k.replace('/tcp', '') for k in port_data.keys()]
