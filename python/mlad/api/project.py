import json
import requests

class Project():
    def __init__(self, token, url):
        self.token = token
        self.url = f'{url}/project'

    def get(self):
        url = self.url
        header = {'token': self.token}
        res = requests.get(url=url,headers=header)
        res.raise_for_status()
        return res.json()    

    def create(self, project, base_labels, extra_envs=[], 
            swarm=True, allow_reuse=False):
        url = self.url
        header = {'token': self.token}
        with requests.post(url=url,headers=header,
            json={'project':project,'base_labels':base_labels,
                'extra_envs':extra_envs},
            params={'swarm':swarm, 'allow_reuse': allow_reuse}, stream=True) as res:
            for _ in res.iter_content(1024):
                res = _.decode()
                dict_res = json.loads(res)
                yield dict_res

    def inspect(self, project_key):
        url = f'{self.url}/{project_key}'
        header = {'token': self.token}
        res = requests.get(url=url, headers=header)
        res.raise_for_status()
        return res.json()

    def delete(self, project_key):
        url = f'{self.url}/{project_key}'
        header = {'token': self.token}
        with requests.delete(url=url, stream=True, headers=header) as res:
            for _ in res.iter_content(1024):
                res = _.decode()
                dict_res = json.loads(res)
                yield dict_res

    def log(self, project_key, tail='all', 
            follow=False, timestamps=False, names_or_ids=[]):
        url = f'{self.url}/{project_key}/logs'
        params = {'tail':tail, 'follow':follow, 'timestamps':timestamps,
            'names_or_ids':names_or_ids}
        header = {'token': self.token}
        
        with requests.get(url=url,params=params, stream=True, headers=header) as res:
            for _ in res.iter_content(1024):
                log = _.decode()
                dict_log = json.loads(log)
                yield dict_log
