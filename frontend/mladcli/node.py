import sys, os
import requests
from pathlib import Path
from mladcli.libs import utils, docker_controller as docker, interrupt_handler
import mladcli.default as default

def list():
    nodes = docker.node_list()
    columns = [('ID', 'HOSTNAME', 'ADDRESS', 'ROLE', 'STATE', 'AVAILABILITY', 'ENGINE', 'LABELS')]
    for node in nodes:
        ID = node['ID'][:10]
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
    docker.node_enable(ID)
    print('Updated.')

def disable(ID):
    docker.node_disable(ID)
    print('Updated.')

def label_add(node, **kvs):
    docker.node_label_add(node, **kvs)
    print('Added.')

def label_rm(node, *keys):
    docker.node_label_rm(node, *keys)
    print('Removed.')
