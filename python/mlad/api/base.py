import requests

from typing import Optional, Dict

from .exceptions import raise_error


class APIBase:

    def __init__(self, config, prefix):
        self.baseurl = f'{config.apiserver.address}/api/v1/{prefix}'
        self.headers = {'session': config.session}
        self.raise_error = raise_error

    def _get(self, path: str, params: Optional[Dict] = None,
             raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        res = requests.get(url=url, headers=self.headers, params=params,
                           timeout=timeout, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()

    def _post(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
              raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        res = requests.post(url=url, headers=self.headers, params=params, json=body,
                            timeout=timeout, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()

    def _delete(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
                raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        res = requests.delete(url=url, headers=self.headers, params=params, json=body,
                              timeout=timeout, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()

    def _put(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
             raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        res = requests.put(url=url, headers=self.headers, params=params, json=body,
                           timeout=timeout, stream=stream)
        self.raise_error(res)
        return res if raw else res.json()
