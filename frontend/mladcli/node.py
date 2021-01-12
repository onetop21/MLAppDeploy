import sys, os
import requests
from pathlib import Path
from mladcli.libs import utils
from mladcli.libs import docker_controller as ctlr
from mladcli.libs import interrupt_handler
import mladcli.default as default

def list():
    cli = ctlr.get_docker_client()
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
    cli = ctlr.get_docker_client()
    ctlr.enable_node(cli, ID)
    print('Updated.')

def disable(ID):
    cli = ctlr.get_docker_client()
    ctlr.disable_node(cli, ID)
    print('Updated.')

def label_add(node, **kvs):
    cli = ctlr.get_docker_client()
    ctlr.add_node_labels(cli, node, **kvs)
    print('Added.')

def label_rm(node, *keys):
    cli = ctlr.get_docker_client()
    ctlr.remove_node_labels(node, *keys)
    print('Removed.')
