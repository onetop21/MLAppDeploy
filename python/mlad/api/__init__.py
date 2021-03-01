import os
import sys
from .auth import Auth
from .node import Node
from .service import Service
from .project import Project

API_PREFIX = '/api/v1'

class API:
    def __init__(self, url=None, token=None):
        self.token = token
        if not url:
            host = os.environ.get('NODE_HOSTNAME', 'localhost')
            self.url = f'http://{host}:8440{API_PREFIX}'
        else:
            self.url = f"{url}{API_PREFIX}"

    def __enter__(self):
        return self

    def __exit__(self, ety, va, tb):
        return False

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
