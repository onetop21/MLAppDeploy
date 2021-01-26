import requests
from . import URL_PREFIX

PROJECT_URL = f'{URL_PREFIX}/project'

def get(project_key, labels=None):
    url = f'{PROJECT_URL}/{project_key}/service'
    res = requests.get(url=url, params={'labels':labels})
    res.raise_for_status()
    return res.json()

def create(project_key, services):
    url = f'{PROJECT_URL}/{project_key}/service'
    res = requests.post(url=url, json={'services':services})
    #services = [{'name':'',..},{'name',..}]
    res.raise_for_status()
    return res.json()

def inspect(project_key, service_id):
    url = f'{PROJECT_URL}/{project_key}/service/{service_id}'
    res = requests.get(url=url)
    res.raise_for_status()
    return res.json()

def get_tasks(project_key, service_id):
    url = f'{PROJECT_URL}/{project_key}/service/{service_id}/tasks'
    res = requests.get(url=url)
    res.raise_for_status()
    return res.json()  

def scale(project_key, service_id, scale_spec):
    url = f'{PROJECT_URL}/{project_key}/service/{service_id}/scale'
    res = requests.put(url=url, json={'scale_spec':scale_spec})
    res.raise_for_status()
    print(res.json()['message'])

def remove(project_key, service_id):
    url = f'{PROJECT_URL}/{project_key}/service/{service_id}'
    res = requests.delete(url=url)
    res.raise_for_status()
    print(res.json()['message'])

