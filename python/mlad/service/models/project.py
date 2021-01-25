from typing import Any
from pydantic import BaseModel

class Project(BaseModel):
    name: str
    version: str
    author: str

class CreateRequest(BaseModel):
    project: Project
    workspace: str
    username: str
    extra_envs: dict
