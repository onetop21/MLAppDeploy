import requests

from typing import Optional, Dict

from .exception import raise_error


class APIBase:

    def __init__(self, config):
        self.baseurl = f'{config.apiserver.address}/api/v1'
        self.headers = {'session': config.session}
        self.raise_error = raise_error

    def _get(self, path: str, params: Optional[Dict] = None,
             raw: bool = False, stream: bool = False):
        url = f'{self.baseurl}{path}'
        res = requests.get(url=url, headers=self.headers, params=params,
                           timeout=3, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()

    def _post(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
              raw: bool = False, stream: bool = False):
        url = f'{self.baseurl}{path}'
        res = requests.post(url=url, headers=self.headers, params=params, json=body,
                            timeout=3, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()

    def _delete(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
                raw: bool = False, stream: bool = False):
        url = f'{self.baseurl}{path}'
        res = requests.delete(url=url, headers=self.headers, params=params, json=body,
                              timeout=3, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()

    def _put(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
             raw: bool = False, stream: bool = False):
        url = f'{self.baseurl}{path}'
        res = requests.put(url=url, headers=self.headers, params=params, json=body,
                           timeout=3, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()
