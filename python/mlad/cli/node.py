import sys, os
import requests
from pathlib import Path
from mlad.cli.libs import utils
from mlad.cli.libs import interrupt_handler
from mlad.api import API
from mlad.api.exception import APIError, NotFound

def list(no_trunc):
    config = utils.read_config()
    try:
        with API(config.mlad.address, config.mlad.token.admin) as api:
            nodes = [api.node.inspect(_) for _ in api.node.get()]
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

def enable(ID):
    config = utils.read_config()
    try:
        with API(config.mlad.address, config.mlad.token.admin) as api:
            api.node.enable(ID)
    except Exception as e:
        print(e)
        sys.exit(1)
    print('Updated.')

def disable(ID):
    config = utils.read_config()
    try:
        with API(config.mlad.address, config.mlad.token.admin) as api:
            api.node.disable(ID)
    except Exception as e:
        print(e)
        sys.exit(1)
    print('Updated.')

def label_add(node, **kvs):
    config = utils.read_config()
    try:
        with API(config.mlad.address, config.mlad.token.admin) as api:
            api.node.add_label(node, **kvs)
    except Exception as e:
        print(e)
        sys.exit(1)
    print('Added.')

def label_rm(node, *keys):
    config = utils.read_config()
    try:
        with API(config.mlad.address, config.mlad.token.admin) as api:
            api.node.delete_label(node, *keys)
    except Exception as e:
        print(e)
        sys.exit(1)
    print('Removed.')
