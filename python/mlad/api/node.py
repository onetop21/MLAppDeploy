from typing import Optional

from .base import APIBase


class Node(APIBase):
    def __init__(self, address: Optional[str], session: Optional[str]):
        super().__init__(address, session, 'node')

    def list(self):
        return self._get('/list')

    def resource(self, names, no_trunc):
        params = {'names': names, 'no_trunc': no_trunc}
        return self._get('/resource', params=params)

    def resource_by_session(self):
        return self._get('/resource/session')
