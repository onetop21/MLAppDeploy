import json


class AlreadyExist(Exception):
    pass


class Duplicated(Exception):
    pass


class TokenError(Exception):
    pass


class NotSupportURL(Exception):
    pass


class NotFound(Exception):
    pass


class APIError(Exception):
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


class NamespaceAlreadyExistError(Exception):

    def __init__(self, key: str):
        self.key = key

    def __str__(self):
        return f'Already exist the namespace, key: [{self.key}]'


class DockerError(Exception):

    def __str__(self):
        return 'Invalid docker environment, please install a docker daemon.'


class DeprecatedError(Exception):

    def __init__(self, option: str):
        self.option = option

    def __str__(self):
        return f'Cannot deploy app for deprecated kind \'{self.option}\'.'


class DockerNotFoundError(Exception):

    def __str__(self):
        return 'Need to install the docker daemon.'
