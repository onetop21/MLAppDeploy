import os
import sys
from .node import Node
from .service import Service
from .project import Project

API_PREFIX = '/api/v1'


class API:
    def __init__(self, url=None, session=None):
        self.session = session
        if not url:
            host = 'mlad-service.mlad'
            port = '8440'
            self.url = f'http://{host}:{port}{API_PREFIX}'
        else:
            self.url = f"{url}{API_PREFIX}"

    def __enter__(self):
        return self

    def __exit__(self, ety, va, tb):
        return False

    @property
    def node(self):
        return Node(self.url, self.session)

    @property
    def project(self):
        return Project(self.url, self.session)

    @property
    def service(self):
        return Service(self.url, self.session)
