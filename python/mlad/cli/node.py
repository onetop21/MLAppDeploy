import sys

from mlad.cli.libs import utils
from mlad.cli.config import get_context
from mlad.cli.exceptions import PluginUninstalledError
from mlad.api import API
from mlad.api.exceptions import APIError
from mlad.core.kubernetes import controller as ctlr


def list(no_trunc: bool):
    try:
        nodes = API.node.list()
    except APIError as e:
        print(e)
        sys.exit(1)
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

    res = API.node.resource(names)
    for name, resources in res.items():
        for i, type in enumerate(resources):
            status = resources[type]
            capacity = status['capacity']
            used = status['used']
            free = status['allocatable']
            if not no_trunc:
                capacity = round(capacity, 1)
                used = round(used, 1) if used is not None else 'NotReady'
                free = round(free, 1)
            else:
                used = status['used'] if used is not None else 'NotReady'
            percentage = int(free / capacity * 100) if capacity else 0
            type = get_unit(type)
            columns.append([name if not i else '', type, capacity, used,
                            f'{free} ({percentage}%)'])
        max_print_length = max([len(column[-1]) for column in columns])
    for column in columns[1:]:
        free_text, percentage_text = column[-1].split(' ')
        space_size = max_print_length - len(free_text) - len(percentage_text)
        column[-1] = f'{free_text}{" " * space_size}{percentage_text}'
    utils.print_table(columns, 'No attached node.', 0 if no_trunc else 32)


def enable(name: str):
    cli = ctlr.get_api_client(context=get_context())
    ctlr.enable_node(name, cli)
    yield f'Node [{name}] is enabled.'


def disable(name: str):
    cli = ctlr.get_api_client(context=get_context())
    ctlr.disable_node(name, cli)
    yield f'Node [{name}] is disabled.'


def delete(name: str):
    cli = ctlr.get_api_client(context=get_context())
    ctlr.delete_node(name, cli)
    yield f'Node [{name}] is deleted.'


def label_add(name: str, **kvs):
    cli = ctlr.get_api_client(context=get_context())
    ctlr.add_node_labels(name, cli, **kvs)
    yield f'Label {kvs} added.'


def label_rm(name: str, *keys):
    cli = ctlr.get_api_client(context=get_context())
    ctlr.remove_node_labels(name, cli, *keys)
    yield f'Label {keys} removed.'
