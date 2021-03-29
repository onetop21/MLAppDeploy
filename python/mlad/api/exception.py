from requests.exceptions import HTTPError


class APIError(Exception):
    msg: str

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class NotFoundError(APIError):
    msg: str

    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def error_from_http_errors(e):
    detail = e.response.json()['detail']
    if e.response.status_code==404:
        cls = NotFoundError
    else:
        cls = APIError
    raise cls(detail)


def raise_error(response):
    try:
        response.raise_for_status()
    except HTTPError as e:
        error_from_http_errors(e)