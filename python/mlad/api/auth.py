import requests
from functools import lru_cache

class Auth():
    def __init__(self, url, token):
        self.url = url
        self.token = token

    def token_create(self, username):
        url = f'{self.url}/admin/user_token'
        header = {'token': self.token}
        res = requests.post(url=url, headers=header,
            json={'username':username})
        res.raise_for_status()
        return res.json()['token']

    @lru_cache(maxsize=None)
    def token_verify(self, token=None):
        url = f'{self.url}/user/auth'
        header = {'user-token': token or self.token}
        res = requests.get(url=url, headers=header)
        res.raise_for_status()
        return res.json()
