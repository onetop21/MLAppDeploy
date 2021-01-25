import sys, os
import requests
from pathlib import Path
from mlad.core.docker import controller as ctlr
from mlad.cli2.libs import utils
from mlad.cli2.libs import interrupt_handler
from mlad.api import node as node_api

#to be removed
token = 'YWRtaW47MjAyMS0wMS0yNVQxNToyNTo0OS43NTAwMDArMDk6MDA7NjU2Y2I5ZWQ3YWZmODEyNDgyOTAxYzFkYmFlMzcyOGMxYjAyOTlmNA=='

def list():
    nodes = [node_api.inspect(token,_) for _ in node_api.get(token)]
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
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.enable(token, ID)
    print('Updated.')

def disable(ID):
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.disable(token, ID)
    print('Updated.')

def label_add(node, **kvs):
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.add_label(token, node, **kvs)
    print('Added.')

def label_rm(node, *keys):
    # config = utils.read_config()
    # cli = ctlr.get_docker_client(config['docker']['host'])
    node_api.delete_label(token, node, *keys)
    print('Removed.')
