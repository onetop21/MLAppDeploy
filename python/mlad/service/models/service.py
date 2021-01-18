from typing import List, Optional
from pydantic import BaseModel

class RestartPolicy(BaseModel):
    condition: str
    delay: int
    max_attempts: int
    window: int

class Quotes(BaseModel):
    cpus: int
    gpus: int
    mems: str

class Deploy(BaseModel):
    quotes: Quotes
    constraints: dict
    restart_policy: RestartPolicy
    replica: int

class Service(BaseModel):
    name: str #service_name
    image: Optional[str] = None
    env: Optional[dict] = None
    depends: Optional[list] = None
    command: Optional[str] = None
    arguments: Optional[str] = None
    #labels: dict
    deploy: Optional[Deploy]=None

class CreateRequest(BaseModel):
    services: List[Service]

class ScaleRequest(BaseModel):
    scale_spec: int
