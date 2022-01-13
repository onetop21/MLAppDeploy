import os
import errno
import socket
import docker
import requests

from docker.types import Mount
from typing import List
from omegaconf import OmegaConf
from mlad.core.exceptions import DockerNotFoundError
from mlad.cli import config as config_core
from mlad.cli.exceptions import (
    MLADBoardNotActivatedError, BoardImageNotExistError, ComponentImageNotExistError,
    MLADBoardAlreadyActivatedError, CannotBuildComponentError
)
from mlad.cli import image as image_core
from mlad.cli.libs import utils

from mlad.cli.validator import validators


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


def activate():
    cli = get_cli()
    config = config_core.get()
    image_tag = _obtain_board_image_tag()
    if image_tag is None:
        raise BoardImageNotExistError

    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        pass
    else:
        raise MLADBoardAlreadyActivatedError

    host_ip = _obtain_host()
    requests.delete(f'{host_ip}:2021/mlad/component', json={
        'name': 'mlad-board'
    })

    yield 'Activating MLAD board.'

    cli.containers.run(
        image_tag,
        environment=[
            f'MLAD_ADDRESS={config.apiserver.address}',
            f'MLAD_SESSION={config.session}',
        ] + config_core.get_env(),
        name='mlad-board',
        auto_remove=True,
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

    host_ip = _obtain_host()
    requests.delete(f'{host_ip}:2021/mlad/component', json={
        'name': 'mlad-board'
    })

    containers = cli.containers.list(filters={
        'label': 'MLAD_BOARD'
    })
    for container in containers:
        container.stop()

    yield 'Successfully deactivate MLAD board.'


def install(file_path: str, no_build: bool):
    cli = get_cli()
    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        raise MLADBoardNotActivatedError

    yield f'Read the component spec from {file_path or "./mlad-project.yml"}.'

    try:
        spec = OmegaConf.load(file_path)
    except Exception:
        raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), file_path)
    spec = validators.validate(OmegaConf.to_container(spec))
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
        ports = component.get('ports', [])
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
    })
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
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    host = s.getsockname()[0]
    s.close()
    return f'http://{host}'


def _obtain_ports(container) -> List[str]:
    lo_cli = get_lo_cli()
    port_data = lo_cli.inspect_container(container.id)['NetworkSettings']['Ports']
    return [k.replace('/tcp', '') for k in port_data.keys()]


def _obtain_board_image_tag():
    cli = get_cli()
    images = cli.images.list(filters={'label': 'MLAD_BOARD'})
    latest_images = [image for image in images
                     if any([tag.endswith('latest') for tag in image.tags])]
    return latest_images[0].tags[-1] if len(latest_images) > 0 else None
