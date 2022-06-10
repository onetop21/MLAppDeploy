import json
from typing import List, Optional, Union
from pydantic import BaseModel


class Quota(BaseModel):
    cpu: Optional[float] = None
    gpu: Optional[int] = None
    mem: Optional[str] = None


class Ingress(BaseModel):
    path: Optional[str]
    rewritePath: bool = True


class Expose(BaseModel):
    port: int
    ingress: Optional[Ingress]


class Mount(BaseModel):
    path: Optional[str]
    mountPath: str
    server: str
    serverPath: str
    options: Optional[List[str]]
    readOnly: bool


class Dependency(BaseModel):
    appName: str
    condition: str = 'Running'


class Component(BaseModel):
    kind = 'Component'
    name: str
    image: Optional[str]
    env: Optional[dict]
    command: Optional[Union[list, str]]
    args: Optional[Union[list, str]]
    mounts: Optional[List[Mount]]
    expose: Optional[List[Expose]]


class Constraint(BaseModel):
    hostname: Optional[str]
    label: Optional[dict]


class AppBase(Component):
    kind = 'App'
    constraints: Optional[Constraint]


class AdvancedBase(AppBase):
    resources: Optional[dict] = None


class App(AppBase):
    restartPolicy: Optional[str] = 'Never'
    quota: Optional[Quota]
    depends: Optional[List[Dependency]]


class JobRunSpec(BaseModel):
    restartPolicy: Optional[str] = 'Never'
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
    restartPolicy: Optional[str] = 'Never'


class AppService(App):
    kind = 'Service'
    scale: Optional[int] = 1
    restartPolicy: Optional[str] = 'Always'


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
            app = json.loads(_.json())
            targets[_.name] = app
            del targets[_.name]['name']
        return targets


class ScaleRequest(BaseModel):
    scale_spec: int


class RemoveRequest(BaseModel):
    apps: List[str]
