import json
from .base import APIBase


class App(APIBase):
    def __init__(self, config):
        super().__init__(config, 'project')

    def get(self, project_key=None, labels=None):
        if project_key is not None:
            path = f'/{project_key}/app'
        else:
            path = '/app'
        return self._get(path, params={'labels': labels})

    def create(self, project_key, apps):
        return self._post(f'/{project_key}/app', body={'apps': apps})

    def inspect(self, project_key, app_id):
        return self._get(f'/{project_key}/app/{app_id}')

    def get_tasks(self, project_key, app_id):
        return self._get(f'/{project_key}/app/{app_id}/tasks')

    def scale(self, project_key, app_id, scale_spec):
        return self._put(f'/{project_key}/app/{app_id}/scale',
                         body={'scale_spec': scale_spec})

    # remove multiple apps using json body
    def remove(self, project_key, apps, stream=False):
        path = f'/{project_key}/app'
        if stream:
            resp = self._delete(path, params={'stream': stream}, body={'apps': apps},
                                stream=True, raw=True, timeout=60)
            for _ in resp.iter_content(1024):
                res = _.decode()
                dict_res = json.loads(res)
                yield dict_res
        else:
            return self._delete(path, params={'stream': stream}, body={'apps': apps})