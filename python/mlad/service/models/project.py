from typing import List, Union, Optional
from pydantic import BaseModel

from mlad.service.models.app import Quota


class CreateRequest(BaseModel):
    base_labels: dict
    project_yaml: dict
    credential: str


class EnvUpdateSpec(BaseModel):
    current: dict
    update: dict


class AppUpdateSpec(BaseModel):
    name: str
    image: Optional[str]
    command: Optional[Union[List[str], str]]
    args: Optional[Union[List[str], str]]
    scale: int = 1
    env: Optional[EnvUpdateSpec]
    quota: Optional[Quota]


class UpdateRequest(BaseModel):
    update_yaml: dict
    update_specs: List[AppUpdateSpec]
