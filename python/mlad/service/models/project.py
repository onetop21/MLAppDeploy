from typing import List, Union, Optional
from pydantic import BaseModel

from mlad.service.models.service import Quota


class CreateRequest(BaseModel):
    base_labels: dict
    extra_envs: list
    project_yaml: Optional[dict] = None
    credential: str


class EnvUpdateSpec(BaseModel):
    current: dict
    update: dict


class ServiceUpdateSpec(BaseModel):
    name: str
    image: str = None
    command: Union[list, str] = None
    args: Union[list, str] = None
    scale: int = 1
    env: EnvUpdateSpec = None
    quota: Quota = None


class UpdateRequest(BaseModel):
    update_yaml: dict
    services: List[ServiceUpdateSpec]


    
    
