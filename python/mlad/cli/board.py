import docker

from mlad.cli import config as config_core

cli = docker.from_env()


def activate() -> None:
    config = config_core.get()
    cli.containers.run(
        '172.19.153.144:5000/mlad/board:latest',
        environment=[
            f'MLAD_ACCESS={config.apiserver.address}'
            f'MLAD_SESSION={config.session}'
        ],
        name='mlad-board',
        auto_remove=True,
        detach=True)


def deactivate() -> None:
    container = cli.containers.get('mlad-board')
    container.stop()
