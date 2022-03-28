from mlad.core import exceptions as core_exceptions
from mlad.cli.libs import utils
from mlad.cli.exceptions import APIServerNotInstalledError
from mlad.cli import config as config_core
from mlad.api import API


def check():
    from mlad.core.kubernetes import controller as ctlr
    checked = {
        'Ingress Controller': {
            'status': False,
            'msgs': ['Run \'helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx && '
                     'helm install ingress-nginx ingress-nginx/ingress-nginx --create-namespace -n ingress-nginx --set controller.service.type=NodePort\'.']
        },
        'Metrics Server': {
            'status': False,
            'msgs': ['Run \'helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ && '
                     'helm install --set \'args={--kubelet-insecure-tls}\' -n kube-system metrics-server metrics-server/metrics-server\'.']
        },
        'NVIDIA Device Plugin': {
            'status': False,
            'msgs': ['Run \'helm repo add nvdp https://nvidia.github.io/k8s-device-plugin && '
                     'helm repo update && helm install nvidia-device-plugin nvdp/nvidia-device-plugin\'.',
                     'Or visit MLAD docs : ...']
        },
        'Node Feature Discovery': {
            'status': False,
            'msgs': ['Run \'kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-feature-discovery/v0.4.1/deployments/static/nfd.yaml\'.']
        },
        'GPU Feature Discovery': {
            'status': False,
            'msgs': ['Run \'helm repo add nvgfd https://nvidia.github.io/gpu-feature-discovery && '
                     'helm repo update && helm install gpu-feature-discovery nvgfd/gpu-feature-discovery '
                     '-n gpu-feature-discovery --create-namespace --set namespace=gpu-feature-discovery\'.']
        },
        'MLAD API Server': {
            'status': False,
            'msgs': ['Run \'helm repo add mlad https://onetop21.github.io/MLAppDeploy/charts && '
                     'helm repo update && helm install mlad mlad/api-server --create-namespace -n mlad\'.']
        },
    }
    config = config_core.get()
    cli = config_core.get_admin_k8s_cli(ctlr)

    yield 'Check installed plugins...'

    # Check ingress controller
    try:
        ctlr.get_k8s_deployment('ingress-nginx-controller', 'ingress-nginx', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['Ingress Controller']['status'] = True

    # Check metrics server
    try:
        ctlr.get_k8s_deployment('metrics-server', 'kube-system', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['Metrics Server']['status'] = True

    # Check nvidia device plugin
    try:
        ctlr.get_k8s_daemonset('nvidia-device-plugin', 'kube-system', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['NVIDIA Device Plugin']['status'] = True

    # Check node feature discovery
    try:
        ctlr.get_k8s_daemonset('nfd', 'node-feature-discovery', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['Node Feature Discovery']['status'] = True
    try:
        ctlr.get_k8s_daemonset('gpu-feature-discovery', 'node-feature-discovery', cli)
    except core_exceptions.NotFound:
        pass
    else:
        checked['GPU Feature Discovery']['status'] = True

    # Check mlad api server
    api_server_address = None
    try:
        api_server_address = config_core.obtain_server_address(config)
    except APIServerNotInstalledError:
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
                yield f' · {line}'

        if plugin == 'MLAD API Server' and status:
            server_version = API.check.check_version()['version']
            yield f' · API Server Version : {server_version}'
            yield f' · API Server Address : {api_server_address}'
