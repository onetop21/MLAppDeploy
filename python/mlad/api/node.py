import requests
from requests.exceptions import HTTPError
from .exception import APIError

class Node():
    def __init__(self, url, token):
        self.url = url   
        self.token = token

    def get(self):
        url = f'{self.url}/node'
        header = {'token':self.token}
        try:
            res = requests.get(url=url, headers=header)
            res.raise_for_status()
        except HTTPError as e:
            raise APIError('Failed to get node list.')
        return res.json()

    def inspect(self, node_id):
        url = f'{self.url}/node/{node_id}'
        header = {'token':self.token}
        try:
            res = requests.get(url=url, headers=header)
            res.raise_for_status()
        except HTTPError as e:
            if e.response.status_code == 404:
                raise APIError('Failed to get the node. Check the node id.')
            else:
                APIError('Failed to get the node.')
        return res.json()

    def enable(self, node_id):
        url = f'{self.url}/node/{node_id}/enable'
        header = {'token': self.token}
        try:
            res = requests.post(url=url, headers=header)
            res.raise_for_status()
        except HTTPError as e:
            raise APIError('Failed to enable the node.')
        return res.json()

    def disable(self, node_id):
        url = f'{self.url}/node/{node_id}/disable'
        header = {'token': self.token}
        try:
            res = requests.post(url=url, headers=header)
            res.raise_for_status()
        except HTTPError as e:
            raise APIError('Failed to disable the node.')
        return res.json()

    def add_label(self, node_id, **labels):
        url = f'{self.url}/node/{node_id}/labels'
        header = {'token': self.token}
        try:  
            res = requests.post(url=url, headers=header, json={'labels':labels})
            res.raise_for_status()
        except HTTPError as e:
            raise APIError('Failed to add label.')
        return res.json()

    def delete_label(self, node_id, *keys):
        url = f'{self.url}/node/{node_id}/labels'
        header = {'token': self.token}
        try:    
            res = requests.delete(url=url, headers=header, json={'keys':keys})
            res.raise_for_status()
        except HTTPError as e:
            raise APIError('Failed to delete label.')
        return res.json()
