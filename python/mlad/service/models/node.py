from typing import Any
from pydantic import BaseModel

class AddLabelRequest(BaseModel):
    labels: dict

class DeleteLabelRequest(BaseModel):
    keys: list