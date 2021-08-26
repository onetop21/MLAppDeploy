import json
from .base import APIBase


class Service(APIBase):
    def __init__(self, config):
        super().__init__(config)

    def get(self, project_key=None, labels=None):
        if project_key is not None:
            path = f'/{project_key}/service'
        else:
            path = '/service'
        return self._get(path, params={'labels': labels})

    def create(self, project_key, services):
        return self._post(f'/{project_key}/service', body={'services': services})

    def inspect(self, project_key, service_id):
        return self._get(f'/{project_key}/service/{service_id}')

    def get_tasks(self, project_key, service_id):
        return self._get(f'/{project_key}/service/{service_id}/tasks')

    def scale(self, project_key, service_id, scale_spec):
        return self._put(f'/{project_key}/service/{service_id}/scale',
                         body={'scale_spec': scale_spec})

    # remove a service using path parameter
    def remove_one(self, project_key, service_id, stream=False):
        path = f'/{project_key}/service/{service_id}'
        if stream:
            resp = self._delete(path, params={'stream': stream}, stream=True, raw=True)
            for _ in resp.iter_content(1024):
                res = _.decode()
                dict_res = json.loads(res)
                yield dict_res
        else:
            return self._delete(path, params={'stream': stream})

    # remove multiple services using json body
    def remove(self, project_key, services, stream=False):
        path = f'/{project_key}/service'
        if stream:
            resp = self._delete(path, params={'stream': stream}, body={'services': services},
                                stream=True, raw=True)
            for _ in resp.iter_content(1024):
                res = _.decode()
                dict_res = json.loads(res)
                yield dict_res
        else:
            return self._delete(path, params={'stream': stream}, body={'services': services})
