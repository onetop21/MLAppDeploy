from mlad.api import API
from mlad.cli.libs import utils
from mlad.cli import config as config_core
from mlad.cli.exceptions import PluginUninstalledError


def list(no_trunc: bool):
    nodes = API.node.list()
    columns = [('ID', 'HOSTNAME', 'ADDRESS', 'ROLE', 'STATE', 'AVAILABILITY', 'ENGINE', 'LABELS')]
    for node in nodes:
        ID = node['id'][:10]
        role = ', '.join(node['role'])
        activate = 'Active' if node['availability'] == 'active' else '-'
        hostname = node['hostname']
        engine = node['engine_version']
        state = node['status']['State']
        address = node['status']['Addr']
        labels = ', '.join([f'{key}={value}' for key, value in node['labels'].items()])
        columns.append((ID, hostname, address, role.title(), state.title(), activate, engine, labels))
    utils.print_table(columns, 'No attached node.', 0 if no_trunc else 32)


def resource(names: list, no_trunc: bool):
    metrics_server_running = API.check.check_metrics_server()

    if not metrics_server_running:
        raise PluginUninstalledError('Metrics server must be installed to load resource information. Please contact the admin.')

    columns = [('HOSTNAME', 'TYPE', 'CAPACITY', 'USED', 'FREE(%)')]

    def get_unit(type):
        res = ''
        if type == 'mem':
            res = f'{type}(Mi)'
        elif type == 'cpu':
            res = f'{type}(cores)'
        elif type == 'gpu':
            res = f'{type}(#)'
        return res

    res = API.node.resource(names, no_trunc)
    for name, resources in res.items():
        for i, type in enumerate(resources):
            status = resources[type]
            capacity = status['capacity']
            used = status['used']
            allocatable = status['allocatable']
            percentage = int(allocatable / capacity * 100) \
                if not isinstance(allocatable, str) and capacity else 0
            type = get_unit(type)
            columns.append([name if not i else '', type, capacity, used,
                            f'{allocatable} ({percentage}%)'])
        max_print_length = max([len(column[-1]) for column in columns])
    for column in columns[1:]:
        free_text, percentage_text = column[-1].split(' ')
        space_size = max_print_length - len(free_text) - len(percentage_text)
        column[-1] = f'{free_text}{" " * space_size}{percentage_text}'
    utils.print_table(columns, 'No attached node.', 0 if no_trunc else 32)


def enable(name: str):
    from mlad.core.kubernetes import controller as ctlr
    cli = config_core.get_admin_k8s_cli(ctlr)
    ctlr.enable_k8s_node(name, cli)
    yield f'Node [{name}] is enabled.'


def disable(name: str):
    from mlad.core.kubernetes import controller as ctlr
    cli = config_core.get_admin_k8s_cli(ctlr)
    ctlr.disable_k8s_node(name, cli)
    yield f'Node [{name}] is disabled.'


def delete(name: str):
    from mlad.core.kubernetes import controller as ctlr
    cli = config_core.get_admin_k8s_cli(ctlr)
    ctlr.delete_k8s_node(name, cli)
    yield f'Node [{name}] is deleted.'


def label_add(name: str, **kvs):
    from mlad.core.kubernetes import controller as ctlr
    cli = config_core.get_admin_k8s_cli(ctlr)
    ctlr.add_k8s_node_labels(name, cli, **kvs)
    yield f'Label {kvs} added.'


def label_rm(name: str, *keys):
    from mlad.core.kubernetes import controller as ctlr
    cli = config_core.get_admin_k8s_cli(ctlr)
    ctlr.remove_k8s_node_labels(name, cli, *keys)
    yield f'Label {keys} removed.'
