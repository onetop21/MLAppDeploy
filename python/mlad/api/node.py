from .base import APIBase


class Node(APIBase):
    def __init__(self, config):
        super().__init__(config, 'node')

    def list(self):
        return self._get('/list')

    def resource(self, names):
        return self._get('/resource', params={'names': names})
