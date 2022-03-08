from mlad.core.exceptions import MLADException


class InvalidSessionError(MLADException):
    def __init__(self, app=False):
        self.target = 'App' if app else 'Project'

    def __str__(self):
        return f'{self.target} can only be removed by ' \
               f'the project creator'


class InvalidLogRequest(MLADException):
    pass


def exception_detail(e):
    exception = e.__class__.__name__
    msg = str(e)

    if 'NotFound' in exception:
        exception = 'NotFound'

    if exception == 'InvalidAppError':
        reason = 'AppNotFound'
    elif exception == 'ProjectNotFoundError':
        reason = 'ProjectNotFound'
    elif exception == 'InvalidLogRequest':
        reason = 'AppNotRunning'
    else:
        reason = 'InternalError'
        # reason = exception

    return {'msg': msg, 'reason': reason}
