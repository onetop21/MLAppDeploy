import os
import socket
import docker
import requests
import click

from typing import List
from omegaconf import OmegaConf
from mlad.cli import config as config_core
from mlad.cli.exceptions import (
    MLADBoardNotActivatedError, BoardImageNotExistError, ComponentImageNotExistError
)
from mlad.cli import image as image_core
from mlad.cli.libs import utils

cli = docker.from_env()
lo_cli = docker.APIClient()


def activate() -> None:
    config = config_core.get()
    image_tag = _obtain_board_image_tag()
    if image_tag is None:
        raise BoardImageNotExistError
    cli.containers.run(
        image_tag,
        environment=[
            f'MLAD_ADDRESS={config.apiserver.address}',
            f'MLAD_SESSION={config.session}',
        ] + config_core.get_env(),
        name='mlad-board',
        auto_remove=True,
        ports={'2021/tcp': '2021'},
        labels=['mlad-board'],
        detach=True)


def deactivate() -> None:
    host_ip = _obtain_host()
    requests.delete(f'{host_ip}:2021/mlad/component', json={
        'name': 'mlad-board'
    })

    containers = cli.containers.list(filters={
        'label': 'mlad-board'
    })
    for container in containers:
        container.stop()


def install(file_path: str, no_build: bool) -> None:
    try:
        cli.containers.get('mlad-board')
    except docker.errors.NotFound:
        raise MLADBoardNotActivatedError

    spec = OmegaConf.load(file_path)
    if no_build:
        built_images = cli.images.list(filter={'label': labels})
        if len(built_images) == 0:
            raise ComponentImageNotExistError
        image = built_images[0]
    else:
        os.environ['MLAD_PRJFILE'] = file_path
        image = image_core.build(False, True, False)

    host_ip = _obtain_host()
    component_specs = []
    for app_name, component in spec.app.items():
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
        labels = ['mlad-board', spec.name, app_name]
        click.echo(f'Run the container [{app_name}]')
        cli.containers.run(
            image.tags[-1],
            environment=env,
            name=app_name,
            auto_remove=True,
            ports={f'{p}/tcp': p for p in ports},
            command=command + args,
            mounts=mounts,
            labels=labels,
            detach=True)

        component_specs.append({
            'name': app_name,
            'hosts': [f'{host_ip}:{p}' for p in ports]
        })

        res = requests.post(f'{host_ip}:2021/mlad/component', json={
            'components': component_specs
        })
        res.raise_for_status()


def uninstall(name: str) -> None:
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
        'label': name
    })
    for container in containers:
        container.stop()


def list():
    containers = cli.containers.list(filters={
        'label': 'mlad-board'
    })
    containers = [c for c in containers if c.name != 'mlad-board']
    ports = [_obtain_port(c) for c in containers]
    columns = [('ID', 'NAME', 'PORT')]
    for container, port in zip(containers, ports):
        columns.append((
            container.short_id,
            container.name,
            port
        ))
    utils.print_table(columns, 'No components installed', 0)


def _obtain_host():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    host = s.getsockname()[0]
    s.close()
    return f'http://{host}'


def _obtain_port(container) -> List[str]:
    port_data = lo_cli.inspect_container(container.id)['NetworkSettings']['Ports']
    return [k.replace('/tcp', '') for k in port_data.keys()]


def _obtain_board_image_tag():
    images = cli.images.list(filters={'label': 'mlad-board'})
    latest_images = [image for image in images
                     if any([tag.endswith('latest') for tag in image.tags])]
    return latest_images[0].tags[0] if len(latest_images) > 0 else None
