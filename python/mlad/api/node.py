from .base import APIBase


class Node(APIBase):
    def __init__(self, config):
        super().__init__(config, 'node')

    def list(self):
        return self._get('/list')

    def resource(self, names, no_trunc):
        params = {'names': names, 'no_trunc': no_trunc}
        return self._get('/resource', params=params)
