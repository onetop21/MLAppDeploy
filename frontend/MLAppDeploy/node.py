import sys, os
import requests
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def list():
    nodes = docker.node_list()
    print('{:12} {:20} {:16} {:9} {:8} {:12} {:10}'.format('ID', 'HOSTNAME', 'ADDRESS', 'ROLE', 'STATE', 'AVAILABILITY', 'ENGINE'))
    for node in nodes:
        ID = node.attrs['ID'][:10]
        role = node.attrs['Spec']['Role']
        activate = node.attrs['Spec']['Availability'] == 'active' 
        hostname = node.attrs['Description']['Hostname']
        engine = node.attrs['Description']['Engine']['EngineVersion']
        state = node.attrs['Status']['State']
        address = node.attrs['Status']['Addr']
        print('{:12} {:20} {:16} {:9} {:8} {:12} {:10}'.format(ID, hostname, address, role.title(), state.title(), 'Active' if activate else '-', engine))

def enable(ID):
    docker.node_enable(ID)
    print('Updated.')

def disable(ID):
    docker.node_disable(ID)
    print('Updated.')

