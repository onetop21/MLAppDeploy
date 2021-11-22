import json
from typing import List
from fastapi import APIRouter, Query, Header, HTTPException
from fastapi.responses import StreamingResponse
from mlad.core.exceptions import APIError
from mlad.service.models import app as app_models
from mlad.service.exceptions import (
    InvalidProjectError, InvalidAppError, InvalidSessionError,
    exception_detail
)
from mlad.core.kubernetes import controller as ctlr


router = APIRouter()


def _check_project_key(project_key, app):
    inspect_key = str(ctlr.inspect_app(app)['key'])
    if project_key == inspect_key:
        return True
    else:
        raise InvalidAppError(project_key, app.metadata.name)


def _check_session_key(project_key, session):
    project = ctlr.get_project_network(project_key=project_key)
    project_session = ctlr.get_project_session(project)
    if project_session == session:
        return True
    else:
        raise InvalidSessionError(app=True)


@router.get('/project/app')
def send_apps_list(labels: List[str] = Query(None), session: str = Header(None)):
    labels_dict = dict()

    if labels is not None:
        labels_dict = {label.split('=')[0]: label.split('=')[1]
                       for label in labels}
    specs = []
    try:
        apps = ctlr.get_apps(extra_filters=labels_dict)
        for app in apps.values():
            spec = ctlr.inspect_app(app)
            specs.append(spec)
        return {'specs': specs}
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get('/project/{project_key}/app')
def send_apps(project_key: str, labels: List[str] = Query(None), session: str = Header(None)):
    labels_dict = dict()
    if labels is not None:
        labels_dict = {label.split("=")[0]: label.split("=")[1]
                       for label in labels}
    specs = []
    try:
        namespace = ctlr.get_namespace(project_key=project_key)
        if not namespace:
            raise InvalidProjectError(project_key)

        apps = ctlr.get_apps(project_key, extra_filters=labels_dict)
        for app in apps.values():
            spec = ctlr.inspect_app(app)
            specs.append(spec)
        return {'specs': specs}
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.post('/project/{project_key}/app')
def create_app(project_key: str, req: app_models.CreateRequest,
               session: str = Header(None)):
    targets = req.json
    try:
        namespace = ctlr.get_namespace(project_key=project_key)
        if not namespace:
            raise InvalidProjectError(project_key)
        apps = ctlr.create_apps(namespace, targets)
        return [ctlr.inspect_app(_) for _ in apps]
    except InvalidProjectError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except APIError as e:
        raise HTTPException(status_code=e.status_code, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get('/project/{project_key}/app/{app_name}')
def inspect_app(project_key: str, app_name: str, session: str = Header(None)):
    try:
        namespace = ctlr.get_namespace(project_key=project_key).metadata.name
        app = ctlr.get_app(app_name, namespace)
        _check_project_key(project_key, app)
        return ctlr.inspect_app(app)
    except InvalidAppError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.get('/project/{project_key}/app/{app_name}/tasks')
def inspect_tasks(project_key: str, app_name: str, session: str = Header(None)):
    try:
        namespace = ctlr.get_namespace(project_key=project_key).metadata.name
        app = ctlr.get_app(app_name, namespace)
        _check_project_key(project_key, app)
        return ctlr.inspect_app(app)['tasks']
    except InvalidAppError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))


@router.put("/project/{project_key}/app/{app_name}/scale")
def scale_app(project_key: str, app_name: str, req: app_models.ScaleRequest, session: str = Header(None)):
    try:
        namespace = ctlr.get_namespace(project_key=project_key).metadata.name
        app = ctlr.get_app(app_name, namespace)
        _check_project_key(project_key, app)
        ctlr.scale_app(app, req.scale_spec)
    except InvalidAppError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    return {'message': f'App {app_name} scale updated'}


@router.delete("/project/{project_key}/app")
def remove_apps(project_key: str, req: app_models.RemoveRequest,
                stream: bool = Query(False), session: str = Header(None)):
    try:
        _check_session_key(project_key, session)
        namespace = ctlr.get_namespace(project_key=project_key).metadata.name
        targets = [ctlr.get_app(name, namespace) for name in req.apps]
        for target in targets:
            _check_project_key(project_key, target)

        class DisconnectHandler:
            def __init__(self):
                self._callbacks = []

            def add_callback(self, callback):
                self._callbacks.append(callback)

            async def __call__(self):
                for cb in self._callbacks:
                    cb()

        handler = DisconnectHandler() if stream else None
        res = ctlr.remove_apps(targets, namespace,
                               disconnect_handler=handler, stream=stream)

        def stringify_response(gen):
            for _ in gen:
                yield json.dumps(_)

    except InvalidAppError as e:
        raise HTTPException(status_code=404, detail=exception_detail(e))
    except InvalidSessionError as e:
        raise HTTPException(status_code=401, detail=exception_detail(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=exception_detail(e))
    if stream:
        return StreamingResponse(stringify_response(res), background=handler)
    else:
        return {'message': 'Apps removed'}
