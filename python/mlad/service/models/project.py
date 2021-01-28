from typing import Any
from pydantic import BaseModel

class Project(BaseModel):
    name: str
    version: str
    author: str

class CreateRequest(BaseModel):
    project: Project
    # workspace: str
    # username: str
    # registry: str
    base_labels: dict
    extra_envs: list
