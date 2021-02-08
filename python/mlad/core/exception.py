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