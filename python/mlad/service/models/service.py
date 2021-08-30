import json
from typing import List, Optional, Union
from pydantic import BaseModel


class Quota(BaseModel):
    cpu: Optional[int]=None
    gpu: Optional[int]=None
    mem: Optional[str]=None


class Ingress(BaseModel):
    name: str = None
    rewritePath: bool = True
    port: str = None


class Component(BaseModel):
    kind = 'Component'
    name: str
    image: Optional[str] = None
    env: Optional[dict] = None
    ports: Optional[list] = None
    command: Optional[Union[list, str]] = None
    args: Optional[Union[list, str]] = None
    ports: Optional[list] = None
    mounts: Optional[list] = None
    ingress: Optional[Ingress] = None


class Constraint(BaseModel):
    hostname: Optional[str] = None
    label: Optional[dict] = None


class AppBase(Component):
    kind = 'App'
    constraints: Optional[Constraint] = None


class AdvancedBase(AppBase):
    resources: Optional[dict] = None


class App(AppBase):
    restartPolicy: Optional[str] = 'never'
    scale: Optional[int] = 1
    quota: Optional[Quota] = None


class JobRunSpec(BaseModel):
    restart_policy: Optional[str] = 'never'
    parallelism: Optional[int] = 1
    completion: Optional[int] = 1


class Job(AdvancedBase):
    kind = 'Job'
    runSpec: Optional[JobRunSpec] = None


class AutoScaler(BaseModel):
    enable: Optional[bool] = False
    min: Optional[int] = 1
    max: Optional[int] = 1
    metrics: Optional[list] = None


class SerivceRunSpec(BaseModel):
    replicas: Optional[int] = 1
    autoscaler: Optional[AutoScaler] = None


class Service(AdvancedBase):
    kind = 'Service'
    runSpec: Optional[SerivceRunSpec] = None


class CreateRequest(BaseModel):
    services: List[dict]

    @property
    def json(self):
        targets = dict()
        for _ in self.services:
            kind = _['kind']
            if kind == 'App':
                _ = App(**_)
            elif kind == 'Job':
                _ = Job(**_)
            elif kind == 'Service':
                _ = Service(**_)
            service = json.loads(_.json())
            targets[_.name]=service
            del targets[_.name]['name']
        return targets


class ScaleRequest(BaseModel):
    scale_spec: int


class RemoveRequest(BaseModel):
    services: List[str]
