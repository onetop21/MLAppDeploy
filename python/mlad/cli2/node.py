import sys, os
import requests
from pathlib import Path
from mlad.core.docker import controller as ctlr
from mlad.cli2.libs import utils
from mlad.cli2.libs import interrupt_handler
from mlad.api import node as node_api

def list():
    config = utils.read_config()
    nodes = [node_api.inspect(config.mlad.token.admin,_) for _ in node_api.get(config.mlad.token.admin)]
    #config = utils.read_config()
    #cli = ctlr.get_docker_client(config['docker']['host'])
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
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.enable(config.mlad.token.admin, ID)
    print('Updated.')

def disable(ID):
    config = utils.read_config()
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.disable(config.mlad.token.admin, ID)
    print('Updated.')

def label_add(node, **kvs):
    config = utils.read_config()
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.add_label(config.mlad.token.admin, node, **kvs)
    print('Added.')

def label_rm(node, *keys):
    config = utils.read_config()
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.delete_label(config.mlad.token.admin, node, *keys)
    print('Removed.')
