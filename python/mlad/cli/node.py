import sys
from mlad.cli.libs import utils
from mlad.api import API
from mlad.api.exceptions import APIError
from mlad.core import exceptions as CoreException
from mlad.core.kubernetes import controller as ctlr


def list(no_trunc):
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


def resource(names=None, no_trunc=False):
    try:
        res = API.node.resource(names)
    except APIError as e:
        print(e)
        sys.exit(1)
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


def enable(ID):
    cli = ctlr.get_api_client(context=ctlr.get_current_context())
    try:
        ctlr.enable_node(ID, cli)
    except CoreException.NotFound as e:
        print(e)
        sys.exit(1)
    except CoreException.APIError as e:
        print(f'Cannot enable node {ID} : {e}')
        sys.exit(1)
    print('Updated.')


def disable(ID):
    cli = ctlr.get_api_client(context=ctlr.get_current_context())
    try:
        ctlr.disable_node(ID, cli)
    except CoreException.NotFound as e:
        print(e)
        sys.exit(1)
    except CoreException.APIError as e:
        print(f'Cannot disable node {ID} : {e}')
        sys.exit(1)
    print('Updated.')


def label_add(node, **kvs):
    cli = ctlr.get_api_client(context=ctlr.get_current_context())
    try:
        ctlr.add_node_labels(node, cli, **kvs)
    except CoreException.NotFound as e:
        print(e)
        sys.exit(1)
    except CoreException.APIError as e:
        print(f'Cannot add label : {e}')
        sys.exit(1)
    print('Added.')


def label_rm(node, *keys):
    cli = ctlr.get_api_client(context=ctlr.get_current_context())
    try:
        ctlr.remove_node_labels(node, cli, *keys)
    except CoreException.NotFound as e:
        print(e)
        sys.exit(1)
    except CoreException.APIError as e:
        print(f'Cannot remove label : {e}')
        sys.exit(1)
    print('Removed.')
