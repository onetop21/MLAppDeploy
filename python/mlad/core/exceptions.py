import json


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


class NamespaceAlreadyExistError(MLADException):

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
