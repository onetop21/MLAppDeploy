class Duplicated(Exception):
    pass


class TokenError(Exception):
    pass


class CannotFoundImageError(Exception):

    def __init__(self, name: str):
        self._name = name

    def __str__(self):
        return f'Cannot find built image of the project [{self._name}].'


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


class MLADBoardNotActivatedError(Exception):

    def __str__(self):
        return 'The MLAD dashboard is not activated.'


class MLADBoardAlreadyActivatedError(Exception):

    def __str__(self):
        return 'The MLAD dashboard is already activated at localhost:2021.'


class BoardImageNotExistError(Exception):

    def __str__(self):
        return 'The MLAD dashboard image does not exist.'


class ComponentImageNotExistError(Exception):

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f'The component [{self.name}] image does not exist.'


class CannotBuildComponentError(Exception):

    def __str__(self):
        return 'The component spec does not have `workspace` property to build an image.'


class DockerNotFoundError(Exception):

    def __str__(self):
        return 'Need to install the docker daemon.'