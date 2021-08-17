import json
from typing import List
from multiprocessing import Queue, Value
from fastapi import APIRouter, Query, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
from starlette.types import Receive
from mlad.service.models import project
from mlad.service.auth import Authorization
from mlad.service.exception import InvalidProjectError, InvalidServiceError, \
    InvalidLogRequest, InvalidSessionError, exception_detail
from mlad.service.libs import utils
from mlad.core.kubernetes import controller as ctlr
from mlad.core import exception


router = APIRouter()
user = Authorization('user')


def _check_session_key(project, session, cli):
    project_session = ctlr.get_project_session(cli, project)
    if project_session == session:
        return True
    else:
        raise InvalidSessionError


@router.post("/project")
def project_create(req: project.CreateRequest, allow_reuse: bool = Query(False),
                   session: str = Header(None)):
    cli = ctlr.get_api_client()

    base_labels = req.base_labels
    extra_envs = req.extra_envs
    credential = req.credential

    try:
        res = ctlr.create_project_network(
            cli, base_labels, extra_envs, credential, allow_reuse=allow_reuse, stream=True)

        def create_project(gen):
            for _ in gen:
                yield json.dumps(_)
    except TypeError as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=exception_detail(e))
    return StreamingResponse(create_project(res))


@router.get("/project")
def projects(extra_labels: str = '', session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        networks = ctlr.get_project_networks(cli, extra_labels.split(',') if extra_labels else [])
        projects = []
        for k, v in networks.items():
            inspect = ctlr.inspect_project_network(cli, v)
            projects.append(inspect)
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return projects


@router.get("/project/{project_key}")
def project_inspect(project_key:str, session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)
        inspect = ctlr.inspect_project_network(cli, network)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return inspect


@router.delete("/project/{project_key}")
def project_remove(project_key:str, session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        _check_session_key(network, session, cli)
        if not network:
            raise InvalidProjectError(project_key)           

        res = ctlr.remove_project_network(cli, network, stream=True)
        def remove_project(gen):
            for _ in gen:
                yield json.dumps(_)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidSessionError as e:
        raise HTTPException(status_code=401, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return StreamingResponse(remove_project(res))


@router.get("/project/{project_key}/logs")
def project_log(project_key: str, tail:str = Query('all'),
                follow: bool = Query(False),
                timestamps: bool = Query(False),
                names_or_ids: list = Query(None),
                session: str = Header(None)):
    cli = ctlr.get_api_client()
    selected = True if names_or_ids else False
    try:
        key = str(project_key).replace('-','')
        network = ctlr.get_project_network(cli, project_key=key)
        if not network:
            raise InvalidProjectError(project_key)

        try:
            targets = ctlr.get_service_with_names_or_ids(cli, key, names_or_ids)
        except exception.NotFound as e:
            if 'running' in str(e):
                raise InvalidLogRequest("Cannot find running services.")
            else:
                services = str(e).split(': ')[1]
                raise InvalidServiceError(project_key, services)

        class disconnectHandler:
            def __init__(self):
                self._callbacks = []
            def add_callback(self, callback):
                self._callbacks.append(callback)
            async def __call__(self):
                for cb in self._callbacks:
                    cb()
        handler = disconnectHandler()

        logs = ctlr.get_project_logs(cli, key,
            tail, follow, timestamps, selected, handler, targets)


        def get_logs(logs):
            for _ in logs:
                _['stream']=_['stream'].decode()
                if timestamps:
                    _['timestamp']=str(_['timestamp'])
                yield json.dumps(_)


    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidServiceError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidLogRequest as e:
        raise HTTPException(status_code=400, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return StreamingResponse(get_logs(logs), background=handler)


@router.get("/project/{project_key}/resource")
def project_resource(project_key: str, session: str = Header(None)):
    cli = ctlr.get_api_client()
    try:
        res = ctlr.get_project_resources(cli, project_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return res
