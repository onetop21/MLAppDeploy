from typing import List, Union
from pydantic import BaseModel

from mlad.service.models.app import Quota


class CreateRequest(BaseModel):
    base_labels: dict
    extra_envs: list
    project_yaml: dict
    credential: str


class EnvUpdateSpec(BaseModel):
    current: dict
    update: dict


class AppUpdateSpec(BaseModel):
    name: str
    image: str = None
    command: Union[list, str] = None
    args: Union[list, str] = None
    scale: int = 1
    env: EnvUpdateSpec = None
    quota: Quota = None


class UpdateRequest(BaseModel):
    update_yaml: dict
    update_specs: List[AppUpdateSpec]
