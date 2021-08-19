class Duplicated(Exception):
    pass


class TokenError(Exception):
    pass


class ContextAlreadyExistError(Exception):

    def __init__(self, name: str):
        self._name = name

    def __str__(self):
        return f'The context [{self._name}] already exists.'


class NotExistContextError(Exception):

    def __init__(self, name: str):
        self._name = name

    def __str__(self):
        return f'There is no context [{self._name}] in contexts.'


class CannotDeleteContextError(Exception):

    def __str__(self):
        return 'The current context cannot be delete, please change the context.'


class InvalidPropertyError(Exception):

    def __init__(self, arg: str):
        self._arg = arg

    def __str__(self):
        return f'There is no matched key in "{self._arg}".'