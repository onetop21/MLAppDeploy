import sys
import json
import requests
from .base import APIBase


class Project(APIBase):
    def __init__(self, config):
        super().__init__(config, 'project')

    def get(self, extra_labels=[]):
        params = {'extra_labels': ','.join(extra_labels)}
        return self._get('/', params=params)

    def create(self, project, base_labels, extra_envs=[], credential=None, allow_reuse=False):
        body = {
            'project': project,
            'base_labels': base_labels,
            'extra_envs': extra_envs,
            'credential': credential
        }
        params = {'allow_reuse': allow_reuse}
        resp = self._post('/', params=params, body=body, raw=True, stream=True)
        res = ''
        for _ in resp.iter_content(1024):
            res += _.decode()
            try:
                dict_res = json.loads(res)
            except json.decoder.JSONDecodeError:
                continue
            else:
                res = ''
            yield dict_res

    def inspect(self, project_key):
        return self._get(f'/{project_key}')

    def delete(self, project_key):
        resp = self._delete(f'/{project_key}', stream=True)
        for _ in resp.iter_content(1024):
            res = _.decode()
            dict_res = json.loads(res)
            yield dict_res

    def log(self, project_key, tail='all',
            follow=False, timestamps=False, names_or_ids=[]):
        params = {'tail': tail, 'follow': follow, 'timestamps': timestamps,
                  'names_or_ids': names_or_ids}
        while True:
            try:
                resp = self._get(f'/{project_key}/logs', params=params, raw=True, stream=True)
                res = ''
                for _ in resp.iter_content(1024):
                    res += _.decode()
                    try:
                        dict_res = json.loads(res)
                    except json.JSONDecodeError as e:
                        log = _.decode()
                        if "stream" in log:
                            # new log line but error occurs cuz tqdm
                            name = log.split('\"name\": \"')[1].split('\"')[0]
                            name_width = int(log.split('\"name_width\": ')[1].split(',')[0])
                            dict_res = {
                                "name": name, "name_width": name_width,
                                "stream": f"[Ignored] Stream Broken : {e}"
                            }
                        else:
                            continue
                    else:
                        res = ''
                    yield dict_res
                break
            except requests.exceptions.ChunkedEncodingError as e:
                print(f"[Retry] {e}", file=sys.stderr)

    def resource(self, project_key):
        project_key = project_key.replace('-', '')
        return self._get(f'/{project_key}/resource')
