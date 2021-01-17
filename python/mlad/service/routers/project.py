from typing import List
import docker
from fastapi import APIRouter, Query, HTTPException
from mlad.service.models import project
from mlad.service.exception import InvalidProjectError
from mlad.core.docker import controller as ctlr

router = APIRouter()

@router.post("/project")
def project_create(req: project.CreateRequest,allow_reuse:bool = Query(False)):
    cli = ctlr.get_docker_client()
    #workspace = 
    # f"{socket.gethostname()}:{os.getcwd()}/mlad-project.yml"
    workspace = req.workspace
    username = req.username
    base_labels = ctlr.make_base_labels(
        workspace, username, dict(req.project))
    try:
        gen = ctlr.create_project_network(
            cli, base_labels, swarm=True, allow_reuse=allow_reuse)          
        for _ in gen:
            if 'stream' in _:
                print(_['stream'])
            if 'result' in _:
                if _['result'] == 'succeed':
                    network = _['output']
                else:
                    print(_['stream'])
                break
    except TypeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ctlr.inspect_project_network(network)

@router.get("/project")
def projects():
    cli = ctlr.get_docker_client()
    try:
        networks = ctlr.get_project_networks(cli)
        projects = [ ctlr.inspect_project_network(v) for k, v in networks.items()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return projects


@router.get("/project/{project_id}")
def project_inspect(project_id:str):
    cli = ctlr.get_docker_client()
    try:
        network = ctlr.get_project_network(cli, project_id=project_id)
        if not network:
            raise InvalidProjectError(project_id)
        inspect = ctlr.inspect_project_network(network)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return inspect

@router.delete("/project/{project_id}")
def project_remove(project_id:str):
    cli = ctlr.get_docker_client()
    try:
        network = ctlr.get_project_network(cli, project_id=project_id)
        if not network:
            raise InvalidProjectError(project_id)
        for _ in ctlr.remove_project_network(cli, network):
            if 'stream' in _:
                print(_['stream'])
            if 'status' in _:
                if _['status'] == 'succeed':
                    print('Network removed')
                break
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {'message': f'project {project_id} removed'}


@router.get("/project/{project_id}/logs")
def project_log():
    pass