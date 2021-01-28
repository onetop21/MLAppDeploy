import json
from typing import List
from fastapi import APIRouter, Query, HTTPException
from mlad.service.models import project
from mlad.service.exception import InvalidProjectError
from mlad.core.docker import controller as ctlr
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/project")
def project_create(req: project.CreateRequest, 
                   allow_reuse: bool = Query(False), 
                   swarm: bool = Query(True)):
    cli = ctlr.get_docker_client()

    base_labels = req.base_labels
    extra_envs = req.extra_envs
    try:
        res = ctlr.create_project_network(
            cli, base_labels, extra_envs, swarm=swarm, 
            allow_reuse=allow_reuse, stream=True)          

        def create_project(gen):
            for _ in gen:
                yield json.dumps(_)
    except TypeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return StreamingResponse(create_project(res))

@router.get("/project")
def projects():
    cli = ctlr.get_docker_client()
    try:
        networks = ctlr.get_project_networks(cli)
        projects = [ ctlr.inspect_project_network(v) for k, v in networks.items()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return projects


@router.get("/project/{project_key}")
def project_inspect(project_key:str):
    cli = ctlr.get_docker_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)
        inspect = ctlr.inspect_project_network(network)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspect

@router.delete("/project/{project_key}")
def project_remove(project_key:str):
    cli = ctlr.get_docker_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)           

        res = ctlr.remove_project_network(cli, network, stream=True)
        def remove_project(gen):
            for _ in gen:
                yield json.dumps(_)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return StreamingResponse(remove_project(res))


@router.get("/project/{project_key}/logs")
def project_log(project_key: str, tail:str = Query('all'),
                follow: bool = Query(False),
                timestamps: bool = Query(False),
                names_or_ids: list = Query(None)):
    cli = ctlr.get_docker_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)

        logs = ctlr.get_project_logs(cli, key, 
            tail, follow, timestamps, names_or_ids)

        def get_logs(logs):
            for _ in logs:
                _['stream']=_['stream'].decode()
                if timestamps:
                    _['timestamp']=str(_['timestamp'])
                yield json.dumps(_)

    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return StreamingResponse(get_logs(logs))

