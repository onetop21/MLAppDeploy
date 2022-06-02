from typing import Optional

from .base import APIBase


class Quota(APIBase):
    def __init__(self, address: Optional[str], session: Optional[str]):
        super().__init__(address, session, 'quota')

    def set_default(self, cpu: float, gpu: int, mem: str):
        return self._post('/set_default', body={
            'cpu': cpu,
            'gpu': gpu,
            'mem': mem
        })

    def set_quota(self, session_key: str, cpu: float, gpu: int, mem: str):
        return self._post('/set', body={
            'cpu': cpu,
            'gpu': gpu,
            'mem': mem,
            'session': session_key
        })
