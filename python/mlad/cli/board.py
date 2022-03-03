import os
import errno
import yaml
import docker
import requests
from requests.exceptions import ConnectionError

from docker.types import Mount
from typing import List
from mlad.core.exceptions import DockerNotFoundError
from mlad.cli import config as config_core
from mlad.cli.exceptions import (
    MLADBoardNotActivatedError, ComponentImageNotExistError,
    MLADBoardAlreadyActivatedError, CannotBuildComponentError
)
from mlad.cli import image as image_core
from mlad.cli.libs import utils


class ValueGenerator:
    def __init__(self, generator):
        self.gen = generator

    def __iter__(self):
        self.value = yield from self.gen

    def get_value(self):
        for x in self:
            pass
        return self.value


def get_cli():
    try:
        return docker.from_env()
    except Exception:
        raise DockerNotFoundError


def get_lo_cli():
    try:
        return docker.APIClient()
    except Exception:
        raise DockerNotFoundError


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

    cli.containers.run(
        image_repository,
        environment=[
            f'MLAD_ADDRESS={config["apiserver"]["address"]}',
            f'MLAD_SESSION={config["session"]}',
        ] + config_core.get_env(),
        name='mlad-board',
        ports={'2021/tcp': '2021'},
        labels=['MLAD_BOARD'],
        detach=True)

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
        raise CannotBuildComponentError

    labels = {
        'MLAD_BOARD': '',
        'COMPONENT_NAME': spec['name']
    }
    if no_build:
        built_images = cli.images.list(filters={'label': labels})
        if len(built_images) == 0:
            raise ComponentImageNotExistError(spec['name'])
        image = built_images[0]
    else:
        image = ValueGenerator(image_core.build(file_path, False, True, False)).get_value()

    host_ip = _obtain_host()
    component_specs = []
    for app_name, component in spec['app'].items():
        if 'image' in component:
            image_name = component['image']
            cli.images.pull(image_name)
            image = cli.images.get(image_name)
        env = {**component.get('env', dict()), **config_core.get_env(dict=True)}
        ports = [expose['port'] for expose in component.get('expose', [])]
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
        cli.containers.run(
            image.tags[-1],
            environment=env,
            name=f'{spec["name"]}-{app_name}',
            ports={f'{p}/tcp': p for p in ports},
            command=command + args,
            mounts=[Mount(source=mount['path'], target=mount['mountPath'], type='bind')
                    for mount in mounts],
            labels=labels,
            detach=True)

        component_specs.append({
            'name': spec['name'],
            'app_name': app_name,
            'hosts': [f'{host_ip}:{p}' for p in ports]
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
    lo_cli = get_lo_cli()
    port_data = lo_cli.inspect_container(container.id)['NetworkSettings']['Ports']
    return [k.replace('/tcp', '') for k in port_data.keys()]
