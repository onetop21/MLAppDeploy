from requests.exceptions import HTTPError


class APIError(Exception):
    def __init__(self, msg, response=None):
        if isinstance(msg, list):
            msg = str(msg)
        self.msg = msg
        self.response = response

    def __str__(self):
        return self.msg

    @property
    def status_code(self):
        if self.response:
            return self.response.status_code

    @property
    def reason(self):
        return self.__class__.__name__


class NotFound(APIError):
    pass


class ProjectNotFound(NotFound):
    pass


class ServiceNotFound(NotFound):
    pass


class InvalidLogRequest(NotFound):
    pass


class InvalidSession(APIError):
    pass


def error_from_http_errors(e):
    detail = e.response.json()['detail'] # msg from mlad service http error
    msg = detail['msg']
    reason = detail['reason']
    if e.response.status_code == 404:
        if reason == 'ProjectNotFound':
            cls = ProjectNotFound
        elif reason == 'ServiceNotFound':
            cls = ServiceNotFound
        else:
            cls = NotFound
    elif e.response.status_code == 401:
        cls = InvalidSession
    elif e.response.status_code == 400:
        if reason == 'ServiceNotRunning':
            cls = InvalidLogRequest
        else:
            cls = APIError
    else:
        cls = APIError
    raise cls(msg, e.response)


def raise_error(response):
    try:
        response.raise_for_status()
    except HTTPError as e:
        error_from_http_errors(e)