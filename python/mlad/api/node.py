import requests
from .exception import raise_error


class Node:
    def __init__(self, url, session):
        self.url = url
        self.headers = {'session': session}

    def list(self):
        res = requests.get(url=f'{self.url}/node/list', headers=self.headers)
        raise_error(res)
        return res.json()

    def resource(self, names):
        res = requests.get(url=f'{self.url}/node/resource', headers=self.headers,
                           params={'names': names})
        raise_error(res)
        return res.json()
