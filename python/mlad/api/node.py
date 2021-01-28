import requests

class Node():
    def __init__(self, url, token):
        self.url = url   
        self.token = token

    def get(self):
        url = f'{self.url}/node'
        header = {'token':self.token}
        res = requests.get(url=url, headers=header)
        res.raise_for_status()
        return res.json()

    def inspect(self, node_id):
        url = f'{self.url}/node/{node_id}'
        header = {'token':self.token}
        res = requests.get(url=url, headers=header)
        res.raise_for_status()
        return res.json()

    def enable(self, node_id):
        url = f'{self.url}/node/{node_id}/enable'
        header = {'token': self.token}
        res = requests.post(url=url, headers=header)
        res.raise_for_status()

    def disable(self, node_id):
        url = f'{self.url}/node/{node_id}/disable'
        header = {'token': self.token}
        res = requests.post(url=url, headers=header)
        res.raise_for_status()

    def add_label(self, node_id, **labels):
        url = f'{self.url}/node/{node_id}/labels'
        header = {'token': self.token}
        res = requests.post(url=url, headers=header, json={'labels':labels})
        res.raise_for_status()

    def delete_label(self, node_id, *keys):
        url = f'{self.url}/node/{node_id}/labels'
        header = {'token': self.token}
        res = requests.delete(url=url, headers=header, json={'keys':keys})
        res.raise_for_status()
