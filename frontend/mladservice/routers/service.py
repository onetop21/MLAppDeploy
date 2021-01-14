from typing import List
from fastapi import APIRouter, Query, HTTPException
from mladservice.models import service
from mladcli.libs import docker_controller as ctlr
from mladservice.exception import InvalidProjectError,InvalidServiceError

router = APIRouter()

def _check_project_id(project_id, service):
    if project_id == str(ctlr.inspect_service(service)['project_id']):
        return True
    else:
        raise InvalidServiceError(project_id, service.short_id)

@router.get("/project/{project_id}/service")
def service_list(project_id:str, 
                 labels: List[str] = Query(None)):
    cli = ctlr.get_docker_client()
    #TODO check labels validation
    #labels = ["MLAD.PROJECT", "MLAD.PROJECT.NAME=lmai"]
    labels_dict=dict()    
    if labels:
        labels_dict = {label.split("=")[0]:label.split("=")[1] 
                       for label in labels}

    try:
        network = ctlr.get_project_network(cli, project_id=project_id)
        if not network:
            raise InvalidProjectError(project_id)

        key = ctlr.inspect_project_network(network)['key']
        key = str(key).replace('-','')
        services = ctlr.get_services(cli, key, extra_filters=labels_dict)        
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return [_.short_id for _ in services.values()]

@router.post("/project/{project_id}/service")
def service_create(project_id:str, req:service.CreateRequest):
    services = req.services
    targets=dict()
    for _ in services:
        targets[_.name]=dict(_)
        del targets[_.name]['name']

    cli = ctlr.get_docker_client()
    try:
        network = ctlr.get_project_network(cli, project_id=project_id)
        if not network:
            raise InvalidProjectError(project_id)

        services = ctlr.create_services(cli, network, targets)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return [_.short_id for _ in services]

@router.get("/project/{project_id}/service/{service_id}")
def service_inspect(project_id:str, service_id:str):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        if _check_project_id(project_id, service):
            inspects = ctlr.inspect_service(service)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspects


@router.get("/project/{project_id}/service/{service_id}/tasks")
def service_tasks(project_id:str, service_id:str):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        if _check_project_id(project_id, service):
             tasks= ctlr.inspect_service(
                ctlr.get_service(cli, service_id))['tasks']           
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return tasks


@router.put("/project/{project_id}/service/{service_id}/scale")
def service_scale(project_id:str, service_id:str, 
                  req: service.ScaleRequest):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        if _check_project_id(project_id, service):
            service.scale(req.scale_spec)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message':'scale updated'}

@router.delete("/project/{project_id}/service/{service_id}")
def service_remove(project_id:str, service_id:str):
    cli = ctlr.get_docker_client()
    try:
        service = ctlr.get_service(cli, service_id)
        if _check_project_id(project_id, service):
            ctlr.remove_services(cli, [service])
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message':f'service {service_id} removed'}


