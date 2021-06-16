import requests
from .exception import raise_error

class Node():
    def __init__(self, url, token):
        self.url = url   
        self.token = token

    def get(self):
        url = f'{self.url}/node'
        header = {'token':self.token}
        res = requests.get(url=url, headers=header)
        raise_error(res)
        return res.json()

    def inspect(self, node_id):
        url = f'{self.url}/node/{node_id}'
        header = {'token':self.token}     
        res = requests.get(url=url, headers=header)
        raise_error(res)
        return res.json()

    def enable(self, node_id):
        url = f'{self.url}/node/{node_id}/enable'
        header = {'token': self.token}
        res = requests.post(url=url, headers=header)
        raise_error(res)
        return res.json()

    def disable(self, node_id):
        url = f'{self.url}/node/{node_id}/disable'
        header = {'token': self.token}
        res = requests.post(url=url, headers=header)
        raise_error(res)
        return res.json()

    def add_label(self, node_id, **labels):
        url = f'{self.url}/node/{node_id}/labels'
        header = {'token': self.token}  
        res = requests.post(url=url, headers=header, json={'labels':labels})
        raise_error(res)
        return res.json()

    def delete_label(self, node_id, *keys):
        url = f'{self.url}/node/{node_id}/labels'
        header = {'token': self.token}    
        res = requests.delete(url=url, headers=header, json={'keys':keys})
        raise_error(res)
        return res.json()

    def resource(self, nodes=[]):
        url = f'{self.url}/node/resource'
        header = {'token': self.token}
        params = {'nodes': nodes}
        res = requests.get(url=url, params=params, headers=header)
        raise_error(res)
        return res.json()