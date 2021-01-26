import json
import requests
from . import URL_PREFIX

PROJECT_URL = f'{URL_PREFIX}/project'

def get(token):
    url = f'{PROJECT_URL}'
    header = {'token':token}
    res = requests.get(url=url,headers=header)
    res.raise_for_status()
    return res.json()    

def create(token, project,workspace, username,registry, extra_envs, allow_reuse):
    url = f'{PROJECT_URL}'
    header = {'token':token}
    with requests.post(url=url,headers=header,json={'project':project,
        'workspace':workspace, 'username':username,
        'registry':registry, 'extra_envs':extra_envs},
        params={'allow_reuse': allow_reuse}, stream=True) as res:
        for _ in res.iter_content(1024):
            res = _.decode()
            dict_res = json.loads(res)
            yield dict_res

def inspect(token, project_key):
    url = f'{PROJECT_URL}/{project_key}'
    header = {'token':token}
    res = requests.get(url=url, headers=header)
    res.raise_for_status()
    return res.json()

def delete(token, project_key):
    url = f'{PROJECT_URL}/{project_key}'
    header = {'token':token}
    with requests.delete(url=url, stream=True, headers=header) as res:
        for _ in res.iter_content(1024):
            res = _.decode()
            dict_res = json.loads(res)
            yield dict_res
    # res.raise_for_status()
    # return res.json()

def log(token, project_key, tail='all', 
        follow=False, timestamps=False, names_or_ids=[]):
    url = f'{PROJECT_URL}/{project_key}/logs'
    params = {'tail':tail, 'follow':follow, 'timestamps':timestamps,
        'names_or_ids':names_or_ids}
    header = {'token':token}
    
    with requests.get(url=url,params=params, stream=True, headers=header) as res:
        for _ in res.iter_content(1024):
            log = _.decode()
            dict_log = json.loads(log)
            yield dict_log

    res.raise_for_status()