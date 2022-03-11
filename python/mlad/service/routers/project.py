import traceback
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Header

from mlad.core import exceptions
from mlad.core.exceptions import ProjectNotFoundError, InvalidAppError
from mlad.core.kubernetes import controller as ctlr

from mlad.service.routers import DictStreamingResponse
from mlad.service.exceptions import (
    InvalidLogRequest, InvalidSessionError, exception_detail
)
from mlad.service.models import project


router = APIRouter()


def _check_session_key(namespace, session):
    project_session = ctlr.get_project_session(namespace)
    if project_session == session:
        return True
    else:
        raise InvalidSessionError


@router.post("/project")
def create_project(req: project.CreateRequest, session: str = Header(None)):
    base_labels = req.base_labels
    extra_envs = req.extra_envs
    credential = req.credential
    project_yaml = req.project_yaml

    try:
        res = ctlr.create_k8s_namespace_with_data(base_labels, extra_envs, project_yaml, credential)
        return DictStreamingResponse(res)
    except TypeError as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=400, detail=exception_detail(e))


@router.get("/project")
def projects(extra_labels: str = '', session: str = Header(None)):
    try:
        projects = []
        namespaces = ctlr.get_k8s_namespaces(extra_labels.split(',') if extra_labels else [])
        for namespace in namespaces:
            spec = ctlr.inspect_k8s_namespace(namespace)
            if not spec.get('deleted', False):
                projects.append(spec)
        return projects
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/project/{project_key}")
def inspect_project(project_key: str, session: str = Header(None)):
    try:
        namespace = ctlr.get_k8s_namespace(project_key)
        inspect = ctlr.inspect_k8s_namespace(namespace)
        return inspect
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.delete("/project/{project_key}")
def remove_project(project_key: str, session: str = Header(None)):
    try:
        namespace = ctlr.get_k8s_namespace(project_key)
        _check_session_key(namespace, session)
        res = ctlr.delete_k8s_namespace(namespace)
        return DictStreamingResponse(res)
    except ProjectNotFoundError as e:
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
        ctlr.get_k8s_namespace(project_key)
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

        res = ctlr.get_project_logs(project_key, tail, follow, timestamps, selected, handler, targets)
        return DictStreamingResponse(res, background=handler)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidAppError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidLogRequest as e:
        raise HTTPException(status_code=400, detail=exception_detail(e))
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get("/project/{project_key}/resource")
def send_resources(project_key: str, group_by: Optional[str] = Query('project'),
                   no_trunc: bool = True,
                   session: str = Header(None)):
    try:
        return ctlr.get_project_resources(project_key, group_by, no_trunc)
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.post("/project/{project_key}")
def update_project(project_key: str, req: project.UpdateRequest):
    update_yaml = req.update_yaml
    update_specs = [update_spec.dict() for update_spec in req.update_specs]
    try:
        namespace = ctlr.get_k8s_namespace(project_key)
        ctlr.update_k8s_namespace(namespace, update_yaml)
        res = ctlr.update_apps(namespace, update_yaml, update_specs)
        return [ctlr.inspect_app(_) for _ in res]
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=exception_detail(e))
