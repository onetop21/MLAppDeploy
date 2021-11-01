import json
import traceback
from typing import List
from fastapi import APIRouter, Query, Header, HTTPException
from fastapi.responses import StreamingResponse
from mlad.core.exceptions import APIError
from mlad.service.models import service
from mlad.service.exception import (
    InvalidProjectError, InvalidServiceError, InvalidSessionError,
    exception_detail
)
from mlad.service.libs import utils
from mlad.core.kubernetes import controller as ctlr


router = APIRouter()


def _check_project_key(project_key, service):
    inspect_key = str(ctlr.inspect_service(service)['key']).replace('-','')
    if project_key == inspect_key:
        return True
    else:
        raise InvalidServiceError(project_key, service.short_id)


def _check_session_key(project_key, session):
    project = ctlr.get_project_network(project_key=project_key)
    project_session = ctlr.get_project_session(project)
    if project_session == session:
        return True
    else:
        raise InvalidSessionError(service=True)


@router.get("/project/service")
def services_list(labels: List[str] = Query(None),
                  session: str = Header(None)):
    labels_dict=dict()
   
    if labels:
        labels_dict = {label.split("=")[0]:label.split("=")[1] 
                       for label in labels}
    inspects=[]
    try:
        services = ctlr.get_services(extra_filters=labels_dict)
        for service in services.values():
            inspect = ctlr.inspect_service(service)
            inspects.append(inspect)
        return {'inspects': inspects}
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/project/{project_key}/service")
def service_list(project_key:str, 
                 labels: List[str] = Query(None),
                 session: str = Header(None)):
    #TODO check labels validation
    #labels = ["MLAD.PROJECT", "MLAD.PROJECT.NAME=lmai"]
    labels_dict=dict()
    if labels:
        labels_dict = {label.split("=")[0]:label.split("=")[1] 
                       for label in labels}
    inspects=[] 
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(project_key=key)
        if not network:
            raise InvalidProjectError(project_key)

        services = ctlr.get_services(key, extra_filters=labels_dict)
        for service in services.values():
            inspect = ctlr.inspect_service(service)
            inspects.append(inspect)
        return {'inspects': inspects}
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    #return [_.short_id for _ in services.values()]


@router.post("/project/{project_key}/service")
def service_create(project_key:str, req:service.CreateRequest,
                   session: str = Header(None)):
    targets = req.json
    key = str(project_key).replace('-', '')
    try:
        network = ctlr.get_project_network(project_key=key)
        if not network:
            raise InvalidProjectError(project_key)
        services = ctlr.create_services(network, targets)
        return [ctlr.inspect_service(_) for _ in services]
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except APIError as e:
        raise HTTPException(status_code=e.status_code, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    #return [_.metadata.uid for _ in services]


@router.get("/project/{project_key}/service/{service_name}")
def service_inspect(project_key:str, service_name:str,
                    session: str = Header(None)):
    key = str(project_key).replace('-', '')
    try:
        namespace = ctlr.get_project_network(project_key=project_key).metadata.name
        service = ctlr.get_service(service_name, namespace)
        if _check_project_key(key, service):
            inspect = ctlr.inspect_service(service)
        return inspect
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/project/{project_key}/service/{service_name}/tasks")
def service_tasks(project_key:str, service_name:str,
                  session: str = Header(None)):
    key = str(project_key).replace('-', '')
    try:
        namespace = ctlr.get_project_network(project_key=project_key).metadata.name
        service = ctlr.get_service(service_name, namespace)
        if _check_project_key(key, service):
            tasks = ctlr.inspect_service(service)['tasks']
        return tasks
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.put("/project/{project_key}/service/{service_name}/scale")
def service_scale(project_key:str, service_name:str,
                  req: service.ScaleRequest, session: str = Header(None)):
    key = str(project_key).replace('-','')
    try:
        namespace = ctlr.get_project_network(project_key=project_key).metadata.name
        service = ctlr.get_service(service_name, namespace)
        if _check_project_key(key, service):
            ctlr.scale_service(service, req.scale_spec)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'message':f'service {service_name} scale updated'}


@router.delete("/project/{project_key}/service/{service_name}")
def service_remove(project_key: str, service_name: str,
                   stream: bool = Query(False),
                   session: str = Header(None)):
    try:
        _check_session_key(project_key, session)
        service = ctlr.get_service(name, namespace)
        if _check_project_key(project_key, service):
            res = ctlr.remove_services([service], stream=stream)

        def remove_service(gen):
            for _ in gen:
                yield json.dumps(_)

    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidSessionError as e:
        raise HTTPException(status_code=401, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    if stream:
        return StreamingResponse(remove_service(res))
    else:
        inspect = ctlr.inspect_service(service)
        return {'message': f"service {service_name} removed"}


@router.delete("/project/{project_key}/service")
def services_remove(project_key: str, req: service.RemoveRequest,
                    stream: bool = Query(False),
                    session: str = Header(None)):
    key = str(project_key).replace('-', '')
    try:
        _check_session_key(project_key, session)
        namespace = ctlr.get_project_network(project_key=project_key).metadata.name
        services = [ctlr.get_service(name, namespace)
                    for name in req.services]
        for service in services:
            _check_project_key(project_key, service)

        class disconnectHandler:
            def __init__(self):
                self._callbacks = []
            def add_callback(self, callback):
                self._callbacks.append(callback)
            async def __call__(self):
                for cb in self._callbacks:
                    cb()
        handler = disconnectHandler() if stream else None

        res = ctlr.remove_services(services, handler, stream=stream)

        def remove_service(gen):
            for _ in gen:
                yield json.dumps(_)

    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidSessionError as e:
        raise HTTPException(status_code=401, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))
    if stream:
        return StreamingResponse(remove_service(res), background=handler)
    else:
        return {'message': f"services removed"}
