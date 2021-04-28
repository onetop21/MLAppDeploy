import json
import requests
from .exception import APIError, ServiceNotFound, raise_error

class Service():
    def __init__(self, url):
        self.url = f'{url}/project'
        #self.token = token

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
        #services = [{'name':'',..},{'name':'',..}]
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
        if stream:
            with requests.delete(url=url, stream=True, params={'stream': stream}) as resp:
                if resp.status_code == 200:
                    for _ in resp.iter_content(1024):
                        res = _.decode()
                        dict_res = json.loads(res)
                        yield dict_res
                elif resp.status_code == 404:
                    raise ServiceNotFound(f'Failed to delete service : {resp.json()["detail"]}', resp)
                else:
                    raise APIError(f'Failed to delete service : {resp.json()["detail"]}', resp)
        else:
            res = requests.delete(url=url, params={'stream': stream})
            raise_error(res)
            return res.json()

    # remove multiple services using json body
    def remove(self, project_key, services, stream=False):
        url = f'{self.url}/{project_key}/service'
        if stream:
            with requests.delete(url=url, stream=True, json={'services': services}, params={'stream': stream}) as resp:
                if resp.status_code == 200:
                    for _ in resp.iter_content(1024):
                        res = _.decode()
                        dict_res = json.loads(res)
                        yield dict_res
                elif resp.status_code == 404:
                    raise ServiceNotFound(f'Failed to delete service : {resp.json()["detail"]}', resp)
                else:
                    raise APIError(f'Failed to delete service : {resp.json()["detail"]}', resp)
        else:
            res = requests.delete(url=url, json={'services': services}, params={'stream': stream})
            raise_error(res)
            return res.json()

