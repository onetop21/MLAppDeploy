import json
import requests
from .exception import APIError, ServiceNotFound, InvalidSession, raise_error

class Service:
    def __init__(self, url, session):
        self.url = f'{url}/project'
        self.session = session

    def get(self, project_key=None, labels=None):
        if project_key:
            url = f'{self.url}/{project_key}/service'
            res = requests.get(url=url, params={'labels':labels})
        else:
            url = f'{self.url}/service'
            res = requests.get(url=url, params={'labels':labels})
        raise_error(res)
        return res.json()

    def create(self, project_key, services):
        url = f'{self.url}/{project_key}/service'
        for service in services:
            service['name'] = service['name'].replace('_', '-')
        res = requests.post(url=url, json={'services':services})
        raise_error(res)
        return res.json()

    def inspect(self, project_key, service_id):
        url = f'{self.url}/{project_key}/service/{service_id}'
        res = requests.get(url=url)
        raise_error(res)
        return res.json()

    def get_tasks(self, project_key, service_id):
        url = f'{self.url}/{project_key}/service/{service_id}/tasks'
        res = requests.get(url=url)
        raise_error(res)
        return res.json()

    def scale(self, project_key, service_id, scale_spec):
        url = f'{self.url}/{project_key}/service/{service_id}/scale'
        res = requests.put(url=url, json={'scale_spec':scale_spec})
        raise_error(res)
        return res.json()

    # remove a service using path parameter
    def remove_one(self, project_key, service_id, stream=False):
        url = f'{self.url}/{project_key}/service/{service_id}'
        header = {'session': self.session}
        if stream:
            resp = requests.delete(url=url, headers=header, stream=True,
                                 params={'stream': stream})
            status = resp.status_code
            if status == 200:
                for _ in resp.iter_content(1024):
                    res = _.decode()
                    dict_res = json.loads(res)
                    yield dict_res
            elif status == 404:
                raise ServiceNotFound(f'Failed to delete service : '
                                      f'{resp.json()["detail"]["msg"]}', resp)
            elif status == 401:
                raise ServiceNotFound(f'Failed to delete service : '
                                      f'{resp.json()["detail"]["msg"]}', resp)
            else:
                raise APIError(f'Failed to delete service : '
                               f'{resp.json()["detail"]["msg"]}', resp)
        else:
            res = requests.delete(url=url, params={'stream': stream})
            raise_error(res)
            return res.json()

    # remove multiple services using json body
    def remove(self, project_key, services, stream=False):
        url = f'{self.url}/{project_key}/service'
        header = {'session': self.session}
        if stream:
            resp = requests.delete(url=url, headers=header,
                                 stream=True, json={'services': services},
                                 params={'stream': stream})
            status = resp.status_code
            if status == 200:
                for _ in resp.iter_content(1024):
                    res = _.decode()
                    dict_res = json.loads(res)
                    yield dict_res
            elif status == 404:
                raise ServiceNotFound(f'Failed to delete service : '
                                      f'{resp.json()["detail"]["msg"]}', resp)
            elif status == 401:
                raise ServiceNotFound(f'Failed to delete service : '
                                      f'{resp.json()["detail"]["msg"]}', resp)
            else:
                raise APIError(f'Failed to delete service : '
                               f'{resp.json()["detail"]["msg"]}', resp)
        else:
            res = requests.delete(url=url, headers=header,
                                  json={'services': services},
                                  params={'stream': stream})
            raise_error(res)
            return res.json()

