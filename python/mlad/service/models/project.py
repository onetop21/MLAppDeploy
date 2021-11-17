from typing import Any, List, Union
from pydantic import BaseModel

from mlad.service.models.service import Quota


class CreateRequest(BaseModel):
    base_labels: dict
    extra_envs: list
    project_yaml: dict
    credential: str


class ServiceUpdateSpec(BaseModel):
    name: str
    image: str = None
    command: Union[list, str] = None
    args: Union[list, str] = None
    scale: int = 1
    env: dict = None
    quota: Quota = None


class UpdateRequest(BaseModel):
    update_yaml: dict
    services: List[ServiceUpdateSpec]


    
    
