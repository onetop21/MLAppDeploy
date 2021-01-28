import sys, os
import requests
from pathlib import Path
from mlad.core.docker import controller as ctlr
from mlad.cli2.libs import utils
from mlad.cli2.libs import interrupt_handler
from mlad.api import API

def list():
    config = utils.read_config()
    with API(utils.to_url(config.mlad), config.mlad.token.admin) as api:
        nodes = [api.node.inspect(_) for _ in api.node.get()]
    columns = [('ID', 'HOSTNAME', 'ADDRESS', 'ROLE', 'STATE', 'AVAILABILITY', 'ENGINE', 'LABELS')]
    for node in nodes:
        ID = node['id'][:10]
        role = node['role']
        activate = 'Active' if node['availability'] == 'active' else '-'
        hostname = node['hostname']
        engine = node['engine_version']
        state = node['status']['State']
        address = node['status']['Addr']
        labels = ', '.join([f'{key}={value}' for key, value in node['labels'].items()])
        columns.append((ID, hostname, address, role.title(), state.title(), activate, engine, labels))
    utils.print_table(columns, 'No attached node.')

def enable(ID):
    config = utils.read_config()
    with API(utils.to_url(config.mlad), config.mlad.token.admin) as api:
        api.node.enable(ID)
    print('Updated.')

def disable(ID):
    config = utils.read_config()
    with API(utils.to_url(config.mlad), config.mlad.token.admin) as api:
        api.node.disable(ID)
    print('Updated.')

def label_add(node, **kvs):
    config = utils.read_config()
    with API(utils.to_url(config.mlad), config.mlad.token.admin) as api:
        api.node.add_label(node, **kvs)
    print('Added.')

def label_rm(node, *keys):
    config = utils.read_config()
    with API(utils.to_url(config.mlad), config.mlad.token.admin) as api:
        api.node.delete_label(node, *keys)
    print('Removed.')
