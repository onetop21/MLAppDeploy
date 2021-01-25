import requests
from . import URL_PREFIX

def get(token):
    url = f'{URL_PREFIX}/node'
    header = {'token':token}
    res = requests.get(url=url, headers=header)
    res.raise_for_status()
    return res.json()

def inspect(token, node_id):
    url = f'{URL_PREFIX}/node/{node_id}'
    header = {'token':token}
    res = requests.get(url=url, headers=header)
    res.raise_for_status()
    return res.json()

def enable(token, node_id):
    url = f'{URL_PREFIX}/node/{node_id}/enable'
    header = {'token':token}
    res = requests.post(url=url, headers=header)
    res.raise_for_status()

def disable(token, node_id):
    url = f'{URL_PREFIX}/node/{node_id}/disable'
    header = {'token':token}
    res = requests.post(url=url, headers=header)
    res.raise_for_status()

def add_label(token, node_id, **labels):
    url = f'{URL_PREFIX}/node/{node_id}/labels'
    header = {'token':token}
    res = requests.post(url=url, headers=header, json={'labels':labels})
    res.raise_for_status()

def delete_label(token, node_id, *keys):
    url = f'{URL_PREFIX}/node/{node_id}/labels'
    header = {'token':token}
    res = requests.delete(url=url, headers=header, json={'keys':keys})
    res.raise_for_status()