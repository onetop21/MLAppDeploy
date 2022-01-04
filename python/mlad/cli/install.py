from mlad.core import exceptions as CoreException
from mlad.core.kubernetes import controller as ctlr
from mlad.cli.libs import utils


def check():
    checked = {
        'Ingress Controller': {
            'status': False,
            'info': ['Install ingress controller.']
        },
        'Metrics Server': {
            'status': False,
            'info': ['Run \'helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/ && '
                     'helm install --set \'args={--kubelet-insecure-tls}\' -n kube-system metrics-server metrics-server/metrics-server\'.']
        },
        'NVIDIA Device Plugin': {
            'status': False,
            'info': ['Run \'kubectl create -f ' 
                     'https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.9.0/nvidia-device-plugin.yml\'',
                     'Or visit MLAD docs : ...']
        },
        'Node Feature Discovery': {
            'status': False,
            'info': []
        },
        'MLAD API Server': {
            'status': False,
            'info': ['Run \'mlad install api-server\'.']
        },
    }
    cli = ctlr.get_api_client(context=ctlr.get_current_context())

    yield 'Check installed plugins...'

    # Check ingress controller
    try:
        ctlr.create_ingress(cli, 'mlad', 'mlad-service', 'dummy-ingress', 8440, '/dummy')
    except Exception as e:
        pass
    else:
        ctlr.delete_ingress(cli, 'mlad', 'dummy-ingress')
        checked['Ingress Controller']['status'] = True

    # Check metrics server
    try:
        ctlr.get_deployment(cli, 'metrics-server', 'kube-system')
    except CoreException.NotFound as e:
        pass
    else:
        checked['Metrics Server']['status'] = True

    # Check nvidia device plugin
    try:
        ctlr.get_daemonset(cli, 'nvidia-device-plugin-daemonset', 'kube-system')
    except CoreException.NotFound as e:
        pass
    else:
        checked['NVIDIA Device Plugin']['status'] = True

    # Check node feature discovery
    try:
        ctlr.get_daemonset(cli, 'nfd', 'node-feature-discovery')
    except CoreException.NotFound as e:
        checked['Node Feature Discovery']['info'].append('"nfs" not found. Run \'kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-feature-discovery/v0.4.1/deployments/static/nfd.yaml\'.')
    try:
        ctlr.get_daemonset(cli, 'gpu-feature-discovery', 'node-feature-discovery')
    except CoreException.NotFound as e:
        checked['Node Feature Discovery']['info'].append('"gpu-feature-discovery" not found. Run \'kubectl apply -f https://raw.githubusercontent.com/NVIDIA/gpu-feature-discovery/v0.4.1/deployments/static/gpu-feature-discovery-daemonset.yaml -n node-feature-discovery\'.')
    finally:
        if len(checked['Node Feature Discovery']['info']) == 0:
            checked['NVIDIA Device Plugin']['status'] = True
        else:
            checked['Node Feature Discovery']['info'].append('Or visit MLAD docs : ...')

    # Check mlad api server
    try:
        ctlr.get_deployment(cli, 'mlad-service', 'mlad')
    except CoreException.NotFound as e:
        pass
    else:
        checked['MLAD API Server']['status'] = True

    for plugin, result in checked.items():
        status = result['status']
        info = result['info']

        mark = f'{utils.OK_COLOR}[✓]{utils.CLEAR_COLOR}' if status else \
            f'{utils.INFO_COLOR}[X]{utils.CLEAR_COLOR}'
        yield f'{mark} {plugin}'

        if not status:
            for line in info:
                yield f'˙ {line}'
