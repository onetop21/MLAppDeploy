class APIError(Exception):
    msg : str
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg

class NotFoundError(Exception):
    msg : str
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg    