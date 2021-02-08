import json
import requests
from requests.exceptions import HTTPError
from .exception import APIError, NotFoundError

class Project():
    def __init__(self, url, token):
        self.url = f'{url}/project'
        self.token = token

    def get(self):
        url = self.url
        header = {'token': self.token}
        try:
            res = requests.get(url=url,headers=header)
            res.raise_for_status()
        except HTTPError as e:
            raise APIError('Failed to get projects.')
        return res.json()    

    def create(self, project, base_labels, extra_envs=[], 
            swarm=True, allow_reuse=False):
        url = self.url
        header = {'token': self.token}
        with requests.post(url=url,headers=header,
            json={'project':project,'base_labels':base_labels,
                'extra_envs':extra_envs},
            params={'swarm':swarm, 'allow_reuse': allow_reuse}, stream=True) as resp:
            if resp.status_code == 200:
                for _ in resp.iter_content(1024):
                    res = _.decode()
                    dict_res = json.loads(res)
                    yield dict_res
            else:
                raise APIError(f'Failed to create project : {resp.json()["detail"]}')

    def inspect(self, project_key):
        url = f'{self.url}/{project_key}'
        header = {'token': self.token}
        try:
            res = requests.get(url=url, headers=header)
            res.raise_for_status()
        except HTTPError as e:
            if e.response.status_code == 404:
                raise NotFoundError(res.json())
            else:
                raise APIError(res.json())
        return res.json()

    def delete(self, project_key):
        url = f'{self.url}/{project_key}'
        header = {'token': self.token}
        with requests.delete(url=url, stream=True, headers=header) as resp:
            if resp.status_code == 200:
                for _ in resp.iter_content(1024):
                    res = _.decode()
                    dict_res = json.loads(res)
                    yield dict_res
            elif resp.status_code == 404: 
                raise NotFoundError(f'Failed to delete project : {resp.json()["detail"]}')
            else: 
                raise APIError(f'Failed to delete project : {resp.json()["detail"]}')

    def log(self, project_key, tail='all', 
            follow=False, timestamps=False, names_or_ids=[]):
        url = f'{self.url}/{project_key}/logs'
        params = {'tail':tail, 'follow':follow, 'timestamps':timestamps,
            'names_or_ids':names_or_ids}
        header = {'token': self.token}
        
        with requests.get(url=url,params=params, stream=True, headers=header) as resp:
            if resp.status_code == 200:
                for _ in resp.iter_content(1024):
                    log = _.decode()
                    dict_log = json.loads(log)
                    yield dict_log
            else:
                raise APIError(f'Failed to get logs : {resp.json()["detail"]}')

