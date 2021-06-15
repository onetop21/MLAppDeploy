import requests
from .exception import raise_error

class Resource():
    def __init__(self, url, token):
        self.url = url
        self.token = token

    def get_nodes(self):
        url = f'{self.url}/resource/node'
        header = {'token':self.token}
        res = requests.get(url=url, headers=header)
        raise_error(res)
        return res.json()