from mlad.core.exceptions import MLADException


class InvalidSessionError(MLADException):
    def __init__(self, app=False):
        self.target = 'App' if app else 'Project'

    def __str__(self):
        return f'{self.target} can only be removed by ' \
               f'the project creator'


class InvalidLogRequest(MLADException):
    pass


class VersionCompatabilityError(MLADException):

    def __init__(self, client: str, server: str):
        self.client = client
        self.server = server

    def __str__(self):
        return f'The CLI version [{self.client}] is not compatible with the server version [{self.server}]'


def exception_detail(e):
    exception = e.__class__.__name__
    msg = str(e)

    if exception == 'NotFound':
        reason = 'NotFound'
    elif exception == 'InvalidAppError':
        reason = 'AppNotFound'
    elif exception == 'ProjectNotFoundError':
        reason = 'ProjectNotFound'
    elif exception == 'InvalidLogRequest':
        reason = 'AppNotRunning'
    elif exception == 'InsufficientSessionQuotaError':
        reason = 'InsufficientSessionQuotaError'
    else:
        reason = 'InternalError'
        # reason = exception

    return {'msg': msg, 'reason': reason}
