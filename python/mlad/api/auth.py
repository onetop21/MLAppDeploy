import requests

class Auth():
    def __init__(self, token, url):
        self.token = token
        self.url = url

    def token_create(self, username):
        url = f'{self.url}/admin/user_token'
        header = {'token': self.token}
        res = requests.post(url=url, headers=header,
            json={'username':username})
        res.raise_for_status()
        return res.json()['token']