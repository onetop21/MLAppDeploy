from typing import List, Optional
from pydantic import BaseModel

class RestartPolicy(BaseModel):
    condition: Optional[str]=None
    delay: Optional[int]=None
    max_attempts: Optional[int]=None
    window: Optional[int]=None

class Quota(BaseModel):
    cpus: Optional[int]=None
    gpus: Optional[int]=None
    mems: Optional[str]=None

class Deploy(BaseModel):
    quota: Optional[Quota]= None
    constraints: Optional[dict]=None
    restart_policy: Optional[RestartPolicy]=None
    replicas: Optional[int]=None

class Service(BaseModel):
    name: str #service_name
    # Deprecated: decide type by restart policy.
    #type: Optional[str] = 'job' #job or rc
    image: Optional[str] = None
    env: Optional[dict] = None
    depends: Optional[list] = None
    command: Optional[str] = None
    arguments: Optional[str] = None
    #labels: dict
    ports: Optional[list]=None #k8s Required
    deploy: Optional[Deploy]=None
    # For Plugin
    service_type: Optional[str] = None
    expose: Optional[int] = None


class CreateRequest(BaseModel):
    services: List[Service]
    
    @property
    def json(self):
        import json
        targets = dict()
        for _ in self.services:
            service = json.loads(_.json())
            targets[_.name]=service
            del targets[_.name]['name']
        return targets


class ScaleRequest(BaseModel):
    scale_spec: int


class RemoveRequest(BaseModel):
    services: List[str]
