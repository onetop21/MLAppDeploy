from .base import APIBase


class Node(APIBase):
    def __init__(self, config):
        super().__init__(config)

    def list(self):
        return self._get('/node/list')

    def resource(self, names):
        return self._get('/node/resource', params={'names': names})
