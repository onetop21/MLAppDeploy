class Duplicated(Exception):
    pass


class TokenError(Exception):
    pass


class NotExistContextError(Exception):

    def __init__(self, name):
        self._name = name

    def __str__(self):
        return f'There is no context [{self._name}] in contexts.'
