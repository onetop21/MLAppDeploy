import sys
import os

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
    status_code: int
    msg: str
    def __init__(self, msg, status_code):
        self.msg = msg
        self.status_code = status_code

    def __str__(self):
        return self.msg