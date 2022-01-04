from typing import Any
from pydantic import BaseModel


class CreateRequest(BaseModel):
    base_labels: dict
    extra_envs: list
    credential: str
