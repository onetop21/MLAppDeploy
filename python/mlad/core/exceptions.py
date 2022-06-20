import json
from inspect import signature
from typing import Optional, Callable

from kubernetes.client.rest import ApiException


class MLADException(Exception):
    pass


class Duplicated(MLADException):
    pass


class NotSupportURL(MLADException):
    pass


class NotFound(MLADException):
    pass


class APIError(MLADException):
    # k8s api error
    def __init__(self, msg, status_code):
        self.msg = msg
        self.status_code = status_code

    def __str__(self):
        return self.msg


def handle_k8s_api_error(e):
    if e.headers['Content-Type'] == 'application/json':
        body = json.loads(e.body)
        if body['kind'] == 'Status':
            msg = body['message']
            status = body['code']
        else:
            msg = str(e)
            status = 500
    return msg, status


def handle_k8s_exception(obj: str, namespaced: bool = False):
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            params = list(signature(func).parameters.keys())
            name = args[params.index('name')]
            if namespaced:
                namespace = args[params.index('namespace')]
            try:
                resp = func(*args, **kwargs)
                return resp
            except ApiException as e:
                msg, status = handle_k8s_api_error(e)
                if status == 404:
                    if namespaced:
                        raise NotFound(f'Cannot find {obj} "{name}" in "{namespace}".')
                    else:
                        raise NotFound(f'Cannot find {obj} "{name}".')
                else:
                    raise APIError(msg, status)
        return wrapper
    return decorator


class ProjectNotFoundError(MLADException):
    def __init__(self, project_key):
        self.project_key = project_key

    def __str__(self):
        return f'Cannot find a project [{self.project_key}]'


class InvalidAppError(Exception):
    def __init__(self, project_id, app_id):
        self.project_id = project_id
        self.app_id = app_id

    def __str__(self):
        return (f'Cannot find app {self.app_id} '
                f'in project {self.project_id}')


class NamespaceAlreadyExistError(Exception):

    def __init__(self, key: str):
        self.key = key

    def __str__(self):
        return f'Already exist the namespace, key: [{self.key}]'


class DeprecatedError(MLADException):

    def __init__(self, option: str):
        self.option = option

    def __str__(self):
        return f'Cannot deploy app for deprecated kind \'{self.option}\'.'


class DockerNotFoundError(MLADException):

    def __str__(self):
        return 'Need to install the docker daemon.'


class InvalidMetricUnitError(MLADException):

    def __init__(self, metric, value: str):
        self.metric = metric
        self.value = value

    def __str__(self):
        return f'Metric {self.metric} \'{self.value}\' cannot be processed.'


class InvalidKubeConfigError(MLADException):

    def __init__(self, config_path: str, context_name: Optional[str]):
        self.config_path = config_path
        self.context_name = context_name

    def __str__(self):
        return (
            f'Cannot load K8s API client from config file: \'{self.config_path}\' '
            f'and context name: \'{self.context_name}\''
        )


class InsufficientSessionQuotaError(MLADException):
    def __init__(self, username: str, hostname: str):
        self.username = username
        self.hostname = hostname

    def __str__(self):
        return f'Quota is insufficient, user: {self.username}, hostname: {self.hostname}'


class InvalidCronJobScheduleError(MLADException):
    def __init__(self, msg: str):
        self.msg = msg

    def __str__(self):
        return f'Job schedule format is invalid:\n\t{self.msg}'
