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


class InvalidSessionError(Exception):
    def __init__(self, app=False):
        self.target = 'App' if app else 'Project'

    def __str__(self):
        return f'{self.target} can only be removed by ' \
               f'the project creator'


class InvalidLogRequest(Exception):
    pass


class TokenError(Exception):
    pass


def exception_detail(e):
    exception = e.__class__.__name__
    msg = str(e)

    if 'NotFound' in exception:
        exception = 'NotFound'

    if exception == 'InvalidAppError':
        reason = 'AppNotFound'
    elif exception == 'InvalidProjectError':
        reason = 'ProjectNotFound'
    elif exception == 'InvalidLogRequest':
        reason = 'AppNotRunning'
    elif exception == 'TokenError':
        reason = exception
    else:
        reason = 'InternalError'
        # reason = exception

    return {'msg': msg, 'reason': reason}
