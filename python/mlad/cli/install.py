from mlad.core import exceptions as core_exceptions
from mlad.core.kubernetes import controller as ctlr
from mlad.core.kubernetes import install as installer
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
            'msgs': ['Run \'kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-feature-discovery/v0.4.1/deployments/static/nfd.yaml\'.']
        },
        'GPU Feature Discovery': {
            'status': False,
            'msgs': ['Run \'kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-feature-discovery/v0.4.1/deployments/static/'
                     'gpu-feature-discovery-daemonset.yaml -n node-feature-discovery\'.']
        },
        'MLAD API Server': {
            'status': False,
            'msgs': ['Run \'helm install mlad ./api-server --create-namespace -n mlad\'.']
        },
    }
    cli = ctlr.get_api_client(context=ctlr.get_current_context())

    yield 'Check installed plugins...'

    # Check ingress controller
    try:
        res = ctlr.check_ingress('dummy-ingress', 'mlad', cli)
    except core_exceptions.NotFound:
        ctlr.create_ingress(cli, 'mlad', 'mlad-service', 'dummy-ingress', 8440, '/dummy')
        res = ctlr.check_ingress('dummy-ingress', 'mlad', cli)
    if res:
        ctlr.delete_ingress(cli, 'mlad', 'dummy-ingress')
        checked['Ingress Controller']['status'] = True

    # Check metrics server
    try:
        ctlr.get_deployment('metrics-server', 'kube-system', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['Metrics Server']['status'] = True

    # Check nvidia device plugin
    try:
        ctlr.get_daemonset('nvidia-device-plugin-daemonset', 'kube-system', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['NVIDIA Device Plugin']['status'] = True

    # Check node feature discovery
    try:
        ctlr.get_daemonset('nfd', 'node-feature-discovery', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['Node Feature Discovery']['status'] = True
    try:
        ctlr.get_daemonset('gpu-feature-discovery', 'node-feature-discovery', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['GPU Feature Discovery']['status'] = True

    # Check mlad api server
    try:
        ctlr.get_deployment('mlad-api-server', 'mlad', cli)
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


def _is_running_api_server(cli, beta: bool) -> bool:
    try:
        name = 'mlad-api-server' if not beta else 'mlad-api-server-beta'
        ctlr.get_deployment(name, 'mlad', cli)
    except core_exceptions.NotFound:
        return False
    return True


def deploy_api_server(image_tag: str, ingress: bool, beta: bool):
    cli = ctlr.get_api_client(context=ctlr.get_current_context())
    is_running = _is_running_api_server(cli, beta)
    if not is_running:
        yield 'Create docker registry secret named \'docker-mlad-sc\'.'
        installer.create_docker_registry_secret(cli)

        yield 'Create \'mlad\' namespace.'
        installer.create_mlad_namespace(cli)

        yield 'Create \'mlad-cluster-role\' cluster role.'
        yield 'Create \'mlad-cluster-role-binding\' cluster role binding.'
        installer.create_api_server_role_and_rolebinding(cli)
        yield f'Create \'mlad-service{"-beta" if beta else ""}\' service.'
        installer.create_mlad_service(cli, nodeport=not ingress, beta=beta)
        if not ingress:
            yield f'Check the node port value of the \'mlad-service{"-beta" if beta else ""}\'.'
            yield 'Run \'kubectl get svc -n mlad\'.'
        yield f'Create \'mlad-api-server{"-beta" if beta else ""}\' deployment.'
        installer.create_mlad_api_server_deployment(cli, image_tag, beta=beta)
    else:
        yield f'Patch the \'mlad-service{"-beta" if beta else ""}\' service.'
        installer.patch_mlad_service(cli, nodeport=not ingress, beta=beta)
        if not ingress:
            yield f'Check the NodePort value of the \'mlad-service{"-beta" if beta else ""}\'.'
            yield 'Run \'kubectl get svc -n mlad\'.'

        yield f'Patch the \'mlad-api-server{"-beta" if beta else ""}\' deployment.'
        installer.patch_mlad_api_server_deployment(cli, beta=beta)

    if ingress:
        yield f'Create \'mlad-ingress{"-beta" if beta else ""}\' ingress.'
        installer.create_mlad_ingress(cli, beta=beta)
    else:
        yield f'Delete running \'mlad-ingress{"-beta" if beta else ""}\' ingress.'
        installer.delete_mlad_ingress(cli, beta=beta)
