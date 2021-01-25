import sys, os
import requests
from pathlib import Path
from mlad.core.docker import controller as ctlr
from mlad.cli.libs import utils
from mlad.cli.libs import interrupt_handler

def list():
    config = utils.read_config()
    cli = ctlr.get_docker_client(config['docker']['host'])
    nodes = [ctlr.inspect_node(_) for _ in ctlr.get_nodes(cli).values()]
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
    cli = ctlr.get_docker_client(config['docker']['host'])
    ctlr.enable_node(cli, ID)
    print('Updated.')

def disable(ID):
    config = utils.read_config()
    cli = ctlr.get_docker_client(config['docker']['host'])
    ctlr.disable_node(cli, ID)
    print('Updated.')

def label_add(node, **kvs):
    config = utils.read_config()
    cli = ctlr.get_docker_client(config['docker']['host'])
    ctlr.add_node_labels(cli, node, **kvs)
    print('Added.')

def label_rm(node, *keys):
    config = utils.read_config()
    cli = ctlr.get_docker_client(config['docker']['host'])
    ctlr.remove_node_labels(node, *keys)
    print('Removed.')
