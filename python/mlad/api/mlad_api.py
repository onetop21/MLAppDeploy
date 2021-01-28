from .auth import Auth
from .node import Node
from .service import Service
from .project import Project

class MladAPI():
    def __init__(self, token, url):
        self.token = token
        self.url = url
        self.auth = Auth(self.token, self.url)
        self.node = Node(self.token, self.url)
        self.project = Project(self.token, self.url)
        self.service =Service(self.url)