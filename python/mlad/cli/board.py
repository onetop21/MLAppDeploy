import docker

from mlad.cli import config as config_core

cli = docker.from_env()


def activate() -> None:
    config = config_core.get()
    cli.containers.run(
        '172.19.153.144:5000/mlad/board:latest',
        environment=[
            f'MLAD_ADDRESS={config.apiserver.address}',
            f'MLAD_SESSION={config.session}'
        ],
        name='mlad-board',
        auto_remove=True,
        ports={'2021/tcp': '2021'},
        labels=['mlad-board'],
        detach=True)


def deactivate() -> None:
    containers = cli.containers.list(filters={
        'label': 'mlad-board'
    })
    for container in containers:
        container.stop()
