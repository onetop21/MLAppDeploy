import requests
from .exception import raise_error

class Node:
    def __init__(self, url, session):
        self.url = url   
        self.session = session

    def get(self):
        url = f'{self.url}/node'
        header = {'session':self.session}
        res = requests.get(url=url, headers=header)
        raise_error(res)
        return res.json()

    def inspect(self, node_id):
        url = f'{self.url}/node/{node_id}'
        header = {'session':self.session}
        res = requests.get(url=url, headers=header)
        raise_error(res)
        return res.json()

    def resource(self, nodes=[]):
        url = f'{self.url}/nodes/resource'
        header = {'session': self.session}
        params = {'nodes': nodes}
        res = requests.get(url=url, params=params, headers=header)
        raise_error(res)
        return res.json()