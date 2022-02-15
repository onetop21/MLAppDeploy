from typing import List
from pydantic import BaseModel


class ComponentPostModel(BaseModel):
    name: str
    app_name: str
    hosts: List[str]


class ComponentPostRequestModel(BaseModel):
    components: List[ComponentPostModel]


class ComponentDeleteRequestModel(BaseModel):
    name: str