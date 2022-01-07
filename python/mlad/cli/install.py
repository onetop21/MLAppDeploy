from mlad.core import exceptions as core_exceptions
from mlad.core.kubernetes import controller as ctlr
from mlad.cli.libs import utils


def has_kubeconfig() -> bool:
    try:
        ctlr.get_current_context()
    except core_exceptions.APIError:
        return False
    return True


def check():
    checked = {
        'Ingress Controller': {
            'status': False,
            'msgs': ['Ingress resource does not work. Install ingress controller.',
                     'If ingress controller is running, retry \'mlad install check\'.']
        },
        'Metrics Server': {
            'status': False,
            'msgs': ['Run \'helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ && '
                     'helm install --set \'args={--kubelet-insecure-tls}\' -n kube-system metrics-server metrics-server/metrics-server\'.']
        },
        'NVIDIA Device Plugin': {
            'status': False,
            'msgs': ['Run \'kubectl create -f '
                     'https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.9.0/nvidia-device-plugin.yml\'',
                     'Or visit MLAD docs : ...']
        },
        'Node Feature Discovery': {
            'status': False,
            'msgs': []
        },
        'MLAD API Server': {
            'status': False,
            'msgs': ['Run \'mlad install api-server [IMAGE_TAG]\'.']
        },
    }
    cli = ctlr.get_api_client(context=ctlr.get_current_context())

    yield 'Check installed plugins...'

    # Check ingress controller
    try:
        res = ctlr.check_ingress(cli, 'dummy-ingress', 'mlad')
    except core_exceptions.NotFound:
        ctlr.create_ingress(cli, 'mlad', 'mlad-service', 'dummy-ingress', 8440, '/dummy')
        res = ctlr.check_ingress(cli, 'dummy-ingress', 'mlad')
    if res:
        ctlr.delete_ingress(cli, 'mlad', 'dummy-ingress')
        checked['Ingress Controller']['status'] = True

    # Check metrics server
    try:
        ctlr.get_deployment(cli, 'metrics-server', 'kube-system')
    except core_exceptions.NotFound:
        pass
    else:
        checked['Metrics Server']['status'] = True

    # Check nvidia device plugin
    try:
        ctlr.get_daemonset(cli, 'nvidia-device-plugin-daemonset', 'kube-system')
    except core_exceptions.NotFound:
        pass
    else:
        checked['NVIDIA Device Plugin']['status'] = True

    # Check node feature discovery
    try:
        ctlr.get_daemonset(cli, 'nfd', 'node-feature-discovery')
    except core_exceptions.NotFound:
        checked['Node Feature Discovery']['msgs'].append('"nfs" not found. Run \'kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-feature-discovery/v0.4.1/deployments/static/nfd.yaml\'.')
    try:
        ctlr.get_daemonset(cli, 'gpu-feature-discovery', 'node-feature-discovery')
    except core_exceptions.NotFound:
        checked['Node Feature Discovery']['msgs'].append('"gpu-feature-discovery" not found. Run \'kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-feature-discovery/v0.4.1/deployments/static/gpu-feature-discovery-daemonset.yaml -n node-feature-discovery\'.')
    finally:
        if len(checked['Node Feature Discovery']['msgs']) == 0:
            checked['Node Feature Discovery']['status'] = True
        else:
            checked['Node Feature Discovery']['msgs'].append('Or visit MLAD docs : ...')

    # Check mlad api server
    try:
        ctlr.get_deployment(cli, 'mlad-service', 'mlad')
    except core_exceptions.NotFound:
        pass
    else:
        checked['MLAD API Server']['status'] = True

    for plugin, result in checked.items():
        status = result['status']
        msgs = result['msgs']

        mark = f'{utils.OK_COLOR}[✓]{utils.CLEAR_COLOR}' if status else \
            f'{utils.INFO_COLOR}[X]{utils.CLEAR_COLOR}'
        yield f'{mark} {plugin}'

        if not status:
            for line in msgs:
                yield f'˙ {line}'


def _is_running_api_server(cli) -> bool:
    try:
        ctlr.get_deployment(cli, 'mlad-api-server', 'mlad')
    except core_exceptions.NotFound:
        return False

    return True


def deploy_api_server(image_tag: str, ingress: bool):
    cli = ctlr.get_api_client(context=ctlr.get_current_context())
    is_running = _is_running_api_server(cli)
    if not is_running:
        yield 'Create docker registry secret named \'docker-mlad-sc\'.'
        ctlr.create_docker_registry_secret(cli)

        yield 'Create \'mlad\' namespace.'
        ctlr.create_mlad_namespace(cli)

        yield 'Create \'mlad-cluster-role\' cluster role.'
        yield 'Create \'mlad-cluster-role-binding\' cluster role binding.'
        ctlr.create_api_server_role_and_rolebinding(cli)

        yield 'Create \'mlad-service\' service.'
        ctlr.create_mlad_service(cli, nodeport=not ingress)

        yield 'Create \'mlad-api-server\' deployment.'
        ctlr.create_mlad_api_server_deployment(cli, image_tag)
    else:
        yield 'Patch the \'mlad-service\' service.'
        ctlr.patch_mlad_service(cli, nodeport=not ingress)

        yield 'Patch the \'mlad-api-service\' deployment.'
        ctlr.patch_mlad_api_server_deployment(cli)

    if ingress:
        yield 'Create \'mlad-ingress\' ingress.'
        ctlr.create_mlad_ingress(cli)
    else:
        yield 'Remove running \'mlad-ingress\' ingress.'
        ctlr.delete_mlad_ingress(cli)
