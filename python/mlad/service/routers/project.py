import json
import traceback
from fastapi import APIRouter, Query, HTTPException, Header
from fastapi.responses import StreamingResponse
from mlad.service.models import project
from mlad.service.exceptions import (
    InvalidLogRequest, InvalidSessionError, exception_detail
)
from mlad.core.kubernetes import controller as ctlr
from mlad.core.exceptions import InvalidProjectError, InvalidAppError
from mlad.core import exceptions


router = APIRouter()


def _check_session_key(project, session):
    project_session = ctlr.get_project_session(project)
    if project_session == session:
        return True
    else:
        raise InvalidSessionError


@router.post("/project")
def create_project(req: project.CreateRequest, allow_reuse: bool = Query(False), session: str = Header(None)):
    base_labels = req.base_labels
    extra_envs = req.extra_envs
    credential = req.credential
    project_yaml = req.project_yaml

    try:
        res = ctlr.create_namespace(
            base_labels, extra_envs, project_yaml, credential, allow_reuse=allow_reuse, stream=True)

        def create_project(gen):
            for _ in gen:
                yield json.dumps(_)

        return StreamingResponse(create_project(res))
    except TypeError as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=exception_detail(e))


@router.get("/project")
def projects(extra_labels: str = '', session: str = Header(None)):
    try:
        namespaces = ctlr.get_namespaces(extra_labels.split(',') if extra_labels else [])
        projects = []
        for k, v in namespaces.items():
            spec = ctlr.inspect_namespace(v)
            if not spec.get('deleted', False):
                projects.append(spec)
        return projects
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/project/{project_key}")
def inspect_project(project_key: str, session: str = Header(None)):
    try:
        namespace = ctlr.get_namespace(project_key=project_key)
        if namespace is None:
            raise InvalidProjectError(project_key)
        inspect = ctlr.inspect_namespace(namespace)
        return inspect
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.delete("/project/{project_key}")
def remove_project(project_key: str, session: str = Header(None)):
    try:
        namespace = ctlr.get_namespace(project_key=project_key)
        _check_session_key(namespace, session)
        if namespace is None:
            raise InvalidProjectError(project_key)

        res = ctlr.remove_namespace(namespace, stream=True)

        def remove_project(gen):
            for _ in gen:
                yield json.dumps(_)

        return StreamingResponse(remove_project(res))
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidSessionError as e:
        raise HTTPException(status_code=401, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/project/{project_key}/logs")
def send_project_log(project_key: str, tail: str = Query('all'),
                     follow: bool = Query(False),
                     timestamps: bool = Query(False),
                     names_or_ids: list = Query(None),
                     session: str = Header(None)):

    selected = True if names_or_ids else False
    try:
        namespace = ctlr.get_namespace(project_key=project_key)
        if namespace is None:
            raise InvalidProjectError(project_key)

        try:
            targets = ctlr.get_app_with_names_or_ids(project_key, names_or_ids)
        except exceptions.NotFound as e:
            if 'running' in str(e):
                raise InvalidLogRequest("Cannot find running apps.")
            else:
                apps = str(e).split(': ')[1]
                raise InvalidAppError(project_key, apps)

        class DisconnectHandler:
            def __init__(self):
                self._callbacks = []

            def add_callback(self, callback):
                self._callbacks.append(callback)

            async def __call__(self):
                for cb in self._callbacks:
                    cb()

        handler = DisconnectHandler()

        logs = ctlr.get_project_logs(project_key, tail, follow, timestamps, selected, handler, targets)

        def get_logs(logs):
            for _ in logs:
                _['stream'] = _['stream'].decode()
                if timestamps:
                    _['timestamp'] = str(_['timestamp'])
                yield json.dumps(_)

        return StreamingResponse(get_logs(logs), background=handler)
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidAppError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidLogRequest as e:
        raise HTTPException(status_code=400, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/project/{project_key}/resource")
def send_resources(project_key: str, session: str = Header(None)):
    try:
        return ctlr.get_project_resources(project_key)
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.post("/project/{project_key}")
def update_project(project_key: str, req: project.UpdateRequest):
    update_yaml = req.update_yaml
    apps = req.apps
    try:
        namespace = ctlr.get_namespace(project_key=project_key)
        ctlr.update_namespace(namespace, update_yaml)
        res = ctlr.update_apps(namespace, apps)
        return [ctlr.inspect_app(_) for _ in res]
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))
