import json
from typing import List
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from mlad.core.exception import APIError
from mlad.service.models import service
from mlad.service.exception import InvalidProjectError,InvalidServiceError
from mlad.service.libs import utils
if not utils.is_kube_mode():
    from mlad.core.docker import controller as ctlr
    MODE = 'swarm'
else:
    from mlad.core.kubernetes import controller as ctlr
    MODE = 'kube'
router = APIRouter()

def _check_project_key(project_key, service, cli=None):
    if MODE=='kube':
        inspect_key = str(ctlr.inspect_service(cli, service)['key']).replace('-','')
    else:
        inspect_key = str(ctlr.inspect_service(service)['key']).replace('-','')
    if project_key == inspect_key:
        return True
    else:
        raise InvalidServiceError(project_key, service.short_id)

@router.get("/project/service")
def services_list(labels: List[str] = Query(None)):
    cli = ctlr.get_api_client()
    labels_dict=dict()
   
    if labels:
        labels_dict = {label.split("=")[0]:label.split("=")[1] 
                       for label in labels}
    inspects=[]
    try:
        services = ctlr.get_services(cli, extra_filters=labels_dict)
        for service in services.values():
            if MODE=='kube':
                inspect = ctlr.inspect_service(cli, service)
            else:
                inspect = ctlr.inspect_service(service)
            inspects.append(inspect)    
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'mode':MODE, 'inspects':inspects}

@router.get("/project/{project_key}/service")
def service_list(project_key:str, 
                 labels: List[str] = Query(None)):
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
            if MODE=='kube':
                inspect = ctlr.inspect_service(cli, service)
            else:
                inspect = ctlr.inspect_service(service)
            inspects.append(inspect)      
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'mode':MODE, 'inspects':inspects}
    #return [_.short_id for _ in services.values()]

@router.post("/project/{project_key}/service")
def service_create(project_key:str, req:service.CreateRequest):
    targets = req.json
    cli = ctlr.get_api_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)
        services = ctlr.create_services(cli, network, targets)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except APIError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e.msg))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if utils.is_kube_mode():
        return [_.metadata.uid for _ in services]
    else :
        return [_.short_id for _ in services]

@router.get("/project/{project_key}/service/{service_id}")
def service_inspect(project_key:str, service_id:str):
    cli = ctlr.get_api_client()
    try:
        service = ctlr.get_service(cli, service_id=service_id)
        key = str(project_key).replace('-','')
        if _check_project_key(key, service, cli):
            if MODE=='kube':
                inspects = ctlr.inspect_service(cli, service)
            else:
                inspects = ctlr.inspect_service(service)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspects
    #return {'mode':MODE, 'inspects':inspects}


@router.get("/project/{project_key}/service/{service_id}/tasks")
def service_tasks(project_key:str, service_id:str):
    cli = ctlr.get_api_client()
    try:
        service = ctlr.get_service(cli, service_id=service_id)
        key = str(project_key).replace('-','')
        if _check_project_key(key, service, cli):
            if MODE=='kube':
                tasks= ctlr.inspect_service(cli,service)['tasks']
            else:
                tasks= ctlr.inspect_service(service)['tasks']
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return tasks


@router.put("/project/{project_key}/service/{service_id}/scale")
def service_scale(project_key:str, service_id:str, 
                  req: service.ScaleRequest):
    cli = ctlr.get_api_client()
    key = str(project_key).replace('-','')
    try:
        service = ctlr.get_service(cli, service_id=service_id)
        if _check_project_key(key, service, cli):
            if MODE=='kube':
                ctlr.scale_service(cli, service, req.scale_spec)
            else:
                service.scale(req.scale_spec)
        # if _check_project_key(project_key, service):
        #     service.scale(req.scale_spec)
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message':f'service {service_id} scale updated'}


@router.delete("/project/{project_key}/service/{service_id}")
def service_remove(project_key: str, service_id: str, stream: bool = Query(False)):
    cli = ctlr.get_api_client()
    try:
        service = ctlr.get_service(cli, service_id=service_id)
        if _check_project_key(project_key, service, cli):
            res = ctlr.remove_services(cli, [service], stream=stream)

        def remove_service(gen):
            for _ in gen:
                yield json.dumps(_)

    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if stream:
        return StreamingResponse(remove_service(res))
    else:
        inspect = ctlr.inspect_service(cli, service)
        return {'message': f"service {inspect['name']} removed"}


@router.delete("/project/{project_key}/service")
def services_remove(project_key: str, req: service.RemoveRequest, stream: bool = Query(False)):
    cli = ctlr.get_api_client()
    try:
        services = [ctlr.get_service(cli, service_id=service_id) for service_id in req.services]
        for service in services:
            _check_project_key(project_key, service, cli)
        res = ctlr.remove_services(cli, services, stream=stream)

        def remove_service(gen):
            for _ in gen:
                yield json.dumps(_)

    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if stream:
        return StreamingResponse(remove_service(res))
    else:
        return {'message': f"services removed"}
