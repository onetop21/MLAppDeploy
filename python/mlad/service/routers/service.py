import json
from typing import List
from fastapi import APIRouter, Query, Header, HTTPException
from fastapi.responses import StreamingResponse
from mlad.core.exceptions import APIError
from mlad.service.models import service
from mlad.service.exception import InvalidProjectError,InvalidServiceError, \
    InvalidSessionError, exception_detail
from mlad.service.libs import utils
from mlad.core.kubernetes import controller as ctlr


router = APIRouter()


def _check_project_key(project_key, service, cli=None):
    inspect_key = str(ctlr.inspect_service(cli, service)['key']).replace('-','')
    if project_key == inspect_key:
        return True
    else:
        raise InvalidServiceError(project_key, service.short_id)


def _check_session_key(project_key, session, cli):
    project = ctlr.get_project_network(cli, project_key=project_key)
    project_session = ctlr.get_project_session(cli, project)
    if project_session == session:
        return True
    else:
        raise InvalidSessionError(service=True)


@router.get("/project/service")
def services_list(labels: List[str] = Query(None),
                  session: str = Header(None)):
    cli = ctlr.get_api_client()
    labels_dict=dict()
   
    if labels:
        labels_dict = {label.split("=")[0]:label.split("=")[1] 
                       for label in labels}
    inspects=[]
    try:
        services = ctlr.get_services(cli, extra_filters=labels_dict)
        for service in services.values():
            inspect = ctlr.inspect_service(cli, service)
            inspects.append(inspect)    
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'inspects':inspects}


@router.get("/project/{project_key}/service")
def service_list(project_key:str, 
                 labels: List[str] = Query(None),
                 session: str = Header(None)):
    cli = ctlr.get_api_client()
    #TODO check labels validation
    #labels = ["MLAD.PROJECT", "MLAD.PROJECT.NAME=lmai"]
    labels_dict=dict()
    if labels:
        labels_dict = {label.split("=")[0]:label.split("=")[1] 
                       for label in labels}
    inspects=[] 
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)

        services = ctlr.get_services(cli, key, extra_filters=labels_dict)
        for service in services.values():
            inspect = ctlr.inspect_service(cli, service)
            inspects.append(inspect)      
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'inspects':inspects}
    #return [_.short_id for _ in services.values()]


@router.post("/project/{project_key}/service")
def service_create(project_key:str, req:service.CreateRequest,
                   session: str = Header(None)):
    targets = req.json
    cli = ctlr.get_api_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)
        services = ctlr.create_services(cli, network, targets)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except APIError as e:
        raise HTTPException(status_code=e.status_code, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return [_.metadata.uid for _ in services]



@router.get("/project/{project_key}/service/{service_id}")
def service_inspect(project_key:str, service_id:str,
                    session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        service = ctlr.get_service(cli, service_id=service_id)
        key = str(project_key).replace('-','')
        if _check_project_key(key, service, cli):
            inspects = ctlr.inspect_service(cli, service)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return inspects


@router.get("/project/{project_key}/service/{service_id}/tasks")
def service_tasks(project_key:str, service_id:str,
                  session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        service = ctlr.get_service(cli, service_id=service_id)
        key = str(project_key).replace('-','')
        if _check_project_key(key, service, cli):
            tasks= ctlr.inspect_service(cli,service)['tasks']
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return tasks


@router.put("/project/{project_key}/service/{service_id}/scale")
def service_scale(project_key:str, service_id:str, 
                  req: service.ScaleRequest, session: str = Header(None)):
    cli = ctlr.get_api_client()
    key = str(project_key).replace('-','')
    try:
        service = ctlr.get_service(cli, service_id=service_id)
        if _check_project_key(key, service, cli):
            ctlr.scale_service(cli, service, req.scale_spec)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'message':f'service {service_id} scale updated'}


@router.delete("/project/{project_key}/service/{service_id}")
def service_remove(project_key: str, service_id: str,
                   stream: bool = Query(False),
                   session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        _check_session_key(project_key, session, cli)
        service = ctlr.get_service(cli, service_id=service_id)
        if _check_project_key(project_key, service, cli):
            res = ctlr.remove_services(cli, [service], stream=stream)

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
        inspect = ctlr.inspect_service(cli, service)
        return {'message': f"service {inspect['name']} removed"}


@router.delete("/project/{project_key}/service")
def services_remove(project_key: str, req: service.RemoveRequest,
                    stream: bool = Query(False),
                    session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        _check_session_key(project_key, session, cli)
        services = [ctlr.get_service(cli, service_id=service_id)
                    for service_id in req.services]
        for service in services:
            _check_project_key(project_key, service, cli)

        class disconnectHandler:
            def __init__(self):
                self._callbacks = []
            def add_callback(self, callback):
                self._callbacks.append(callback)
            async def __call__(self):
                for cb in self._callbacks:
                    cb()
        handler = disconnectHandler() if stream else None

        res = ctlr.remove_services(cli, services, handler, stream=stream)

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
        return StreamingResponse(remove_service(res), background=handler)
    else:
        return {'message': f"services removed"}
