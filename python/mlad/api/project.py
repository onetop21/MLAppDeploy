import sys
import json
import requests
from .base import APIBase


def _parse_partial_json(value: str):
    i = 0
    li = 0
    objs = []
    while i < len(value) - 1:
        i += 1
        if value[i] == '}' and (i == len(value) - 1 or value[i + 1] == '{'):
            try:
                objs.append(json.loads(value[li: i + 1]))
                li = i + 1
            except json.JSONDecodeError:
                continue
    return objs, value[li:]


class Project(APIBase):
    def __init__(self, config):
        super().__init__(config, 'project')

    def get(self, extra_labels=[]):
        params = {'extra_labels': ','.join(extra_labels)}
        return self._get('', params=params)

    def create(self, base_labels, extra_envs=[], project_yaml=None, credential=None, allow_reuse=False):
        body = {
            'base_labels': base_labels,
            'extra_envs': extra_envs,
            'project_yaml': project_yaml,
            'credential': credential,
        }
        params = {'allow_reuse': allow_reuse}
        resp = self._post('', params=params, body=body, raw=True, stream=True)
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
        resp = self._delete(f'/{project_key}', stream=True, raw=True)
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
                    res += _.decode('utf-8', 'replace')
                    objs, res = _parse_partial_json(res)
                    for obj in objs:
                        yield obj
                break
            except requests.exceptions.ChunkedEncodingError as e:
                print(f"[Retry] {e}", file=sys.stderr)

    def resource(self, project_key):
        return self._get(f'/{project_key}/resource')

    def update(self, project_key, update_yaml, services):
        body = {
            'update_yaml': update_yaml,
            'services': services
        }
        return self._post(f'/{project_key}', body=body)
