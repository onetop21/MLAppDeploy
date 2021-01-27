import json
from typing import List
from fastapi import APIRouter, Query, HTTPException
from mlad.service.models import service
from mlad.service.exception import InvalidProjectError,InvalidServiceError
from mlad.core.docker import controller as ctlr

router = APIRouter()

def _check_project_key(project_key, service):
    inspect_key = str(ctlr.inspect_service(service)['key']).replace('-','')
    if project_key == inspect_key:
        return True
    else:
        raise InvalidServiceError(project_key, service.short_id)

@router.get("/project/{project_key}/service")
def service_list(project_key:str, 
                 labels: List[str] = Query(None)):
    cli = ctlr.get_docker_client()
    #TODO check labels validation
    #labels = ["MLAD.PROJECT", "MLAD.PROJECT.NAME=lmai"]
    labels_dict=dict()    
    if labels:
        labels_dict = {label.split("=")[0]:label.split("=")[1] 
                       for label in labels}

    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)

        services = ctlr.get_services(cli, key, extra_filters=labels_dict)        
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return [_.short_id for _ in services.values()]

@router.post("/project/{project_key}/service")
def service_create(project_key:str, req:service.CreateRequest):
    targets = req.json

    cli = ctlr.get_docker_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)

        services = ctlr.create_services(cli, network, targets)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [_.short_id for _ in services]

@router.get("/project/{project_key}/service/{service_id}")
def service_inspect(project_key:str, service_id:str):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        key = str(project_key).replace('-','')
        if _check_project_key(key, service):
            inspects = ctlr.inspect_service(service)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspects


@router.get("/project/{project_key}/service/{service_id}/tasks")
def service_tasks(project_key:str, service_id:str):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        key = str(project_key).replace('-','')
        if _check_project_key(key, service):
             tasks= ctlr.inspect_service(
                ctlr.get_service(cli, service_id))['tasks']           
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return tasks


@router.put("/project/{project_key}/service/{service_id}/scale")
def service_scale(project_key:str, service_id:str, 
                  req: service.ScaleRequest):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        if _check_project_key(project_key, service):
            service.scale(req.scale_spec)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message':'scale updated'}

@router.delete("/project/{project_key}/service/{service_id}")
def service_remove(project_key:str, service_id:str):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        if _check_project_key(project_key, service):
            ctlr.remove_services(cli, [service])
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message':f'service {service_id} removed'}


