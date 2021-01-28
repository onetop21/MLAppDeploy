import requests
from . import URL_PREFIX

def token_create(token, username):
    url = f'{URL_PREFIX}/admin/user_token'
    header = {'token': token}
    res = requests.post(url=url, headers=header,
        json={'username':username})
    res.raise_for_status()
    return res.json()['token']