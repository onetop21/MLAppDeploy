import json
from typing import List, Optional, Union
from pydantic import BaseModel


class Quota(BaseModel):
    cpu: Optional[int] = None
    gpu: int = 0
    mem: Optional[str] = None


class Ingress(BaseModel):
    name: str = None
    path: str = None
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
    restartPolicy: Optional[str] = 'never'
    parallelism: Optional[int] = 1
    completion: Optional[int] = 1


class Job(AdvancedBase):
    kind = 'Job'
    runSpec: Optional[JobRunSpec] = None


class ServiceRunSpec(BaseModel):
    replicas: Optional[int] = 1


class Service(AdvancedBase):
    kind = 'Service'
    runSpec: Optional[ServiceRunSpec] = None


###

class AppJob(App):
    kind = 'Job'
    # Never | onFailure
    restartPolicy: Optional[str] = 'never'


class AppService(App):
    kind = 'Service'
    restartPolicy: Optional[str] = 'always'


class CreateRequest(BaseModel):
    apps: List[dict]

    @property
    def json(self):
        targets = dict()
        for _ in self.apps:
            kind = _['kind']
            if kind == 'App':
                _ = App(**_)
            elif kind == 'Job':
                _ = AppJob(**_)
            elif kind == 'Service':
                _ = AppService(**_)
            service = json.loads(_.json())
            targets[_.name] = service
            del targets[_.name]['name']
        return targets


class ScaleRequest(BaseModel):
    scale_spec: int


class RemoveRequest(BaseModel):
    apps: List[str]
