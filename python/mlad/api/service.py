import requests

class Service():
    def __init__(self, url):
        self.url = f'{url}/project'
        #self.token = token

    def get(self, project_key=None, labels=None):
        if project_key:
            url = f'{self.url}/{project_key}/service'
            res = requests.get(url=url, params={'labels':labels})
            res.raise_for_status()
        else:
            url = f'{self.url}/service'
            res = requests.get(url=url, params={'labels':labels})
            res.raise_for_status()
        return res.json()

    def create(self, project_key, services):
        url = f'{self.url}/{project_key}/service'
        res = requests.post(url=url, json={'services':services})
        #services = [{'name':'',..},{'name':'',..}]
        res.raise_for_status()
        return res.json()

    def inspect(self, project_key, service_id):
        url = f'{self.url}/{project_key}/service/{service_id}'
        res = requests.get(url=url)
        res.raise_for_status()
        return res.json()

    def get_tasks(self, project_key, service_id):
        url = f'{self.url}/{project_key}/service/{service_id}/tasks'
        res = requests.get(url=url)
        res.raise_for_status()
        return res.json()

    def scale(self, project_key, service_id, scale_spec):
        url = f'{self.url}/{project_key}/service/{service_id}/scale'
        res = requests.put(url=url, json={'scale_spec':scale_spec})
        res.raise_for_status()
        return res.json()


    def remove(self, project_key, service_id):
        url = f'{self.url}/{project_key}/service/{service_id}'
        res = requests.delete(url=url)
        res.raise_for_status()
        return res.json()

