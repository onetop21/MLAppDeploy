import json

from typing import Optional


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


class InvalidProjectError(Exception):
    def __init__(self, project_id):
        self.project_id = project_id

    def __str__(self):
        return f'Cannot find project {self.project_id}'


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
