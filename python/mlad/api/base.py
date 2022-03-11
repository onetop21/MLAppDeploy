import os

from typing import Optional, Dict

import requests
from requests.exceptions import ConnectionError

from .exceptions import raise_error, ConnectionRefusedError


class APIBase:

    def __init__(self, address: Optional[str], session: Optional[str], prefix: str):
        if address is None:
            self.baseurl = f'{os.environ.get("MLAD_ADDRESS", "localhost:8440")}/api/v1/{prefix}'
        else:
            self.baseurl = f'{address}/api/v1/{prefix}'
        if session is None:
            self.headers = {'session': os.environ.get('MLAD_SESSION', '')}
        else:
            self.headers = {'session': session}
        self.raise_error = raise_error

    def _get(self, path: str, params: Optional[Dict] = None,
             raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        try:
            res = requests.get(url=url, headers=self.headers, params=params,
                               timeout=timeout, stream=stream)
        except ConnectionError:
            raise ConnectionRefusedError(url)
        self.raise_error(res)
        return res if raw else res.json()

    def _post(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
              raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        try:
            res = requests.post(url=url, headers=self.headers, params=params, json=body,
                                timeout=timeout, stream=stream)
        except ConnectionError:
            raise ConnectionRefusedError(url)
        self.raise_error(res)
        return res if raw else res.json()

    def _delete(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
                raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        try:
            res = requests.delete(url=url, headers=self.headers, params=params, json=body,
                                  timeout=timeout, stream=stream)
        except ConnectionError:
            raise ConnectionRefusedError(url)
        self.raise_error(res)
        return res if raw else res.json()

    def _put(self, path: str, params: Optional[Dict] = None, body: Optional[Dict] = None,
             raw: bool = False, stream: bool = False, timeout: int = 30):
        url = f'{self.baseurl}{path}'
        if stream:
            timeout = 1e4
        try:
            res = requests.put(url=url, headers=self.headers, params=params, json=body,
                               timeout=timeout, stream=stream)
        except ConnectionError:
            raise ConnectionRefusedError(url)
        self.raise_error(res)
        return res if raw else res.json()
