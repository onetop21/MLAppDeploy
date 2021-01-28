import sys
from .auth import Auth
from .node import Node
from .service import Service
from .project import Project

API_PREFIX = '/api/v1'
class API:
    def __init__(self, url, token=None):
        self.url = f"{url}{API_PREFIX}"
        self.token = token

    def __enter__(self):
        return self

    def __exit__(self, ety, va, tb):
        return True

    @property
    def auth(self):
        return Auth(self.url, self.token)

    @property
    def node(self):
        return Node(self.url, self.token)

    @property
    def project(self):
        return Project(self.url, self.token)

    @property
    def service(self):
        return Service(self.url)
