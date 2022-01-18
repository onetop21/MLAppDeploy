from mlad.core.exceptions import MLADException


class InvalidURLError(MLADException):
    pass


class ImageNotFoundError(MLADException):

    def __init__(self, name: str):
        self._name = name

    def __str__(self):
        return f'Cannot find built image of the project [{self._name}].'


class ConfigAlreadyExistError(MLADException):

    def __init__(self, name: str):
        self._name = name

    def __str__(self):
        return f'The config [{self._name}] already exists.'


class ConfigNotFoundError(MLADException):

    def __init__(self, name: str):
        self._name = name

    def __str__(self):
        return f'There is no config [{self._name}] in configs.'


class CannotDeleteConfigError(MLADException):

    def __str__(self):
        return 'The current config cannot be deleted, please change the config.'


class InvalidPropertyError(MLADException):

    def __init__(self, arg: str):
        self._arg = arg

    def __str__(self):
        return f'There is no matched key in "{self._arg}".'


class MLADBoardNotActivatedError(MLADException):

    def __str__(self):
        return 'The MLAD dashboard is not activated.'


class MLADBoardAlreadyActivatedError(MLADException):

    def __str__(self):
        return 'The MLAD dashboard is already activated at localhost:2021.'


class BoardImageNotExistError(MLADException):

    def __str__(self):
        return 'The MLAD dashboard image does not exist.'


class ComponentImageNotExistError(MLADException):

    def __init__(self, name):
        self.name = name

    def __str__(self):
        return f'The component [{self.name}] image does not exist.'


class CannotBuildComponentError(MLADException):

    def __str__(self):
        return 'The component spec does not have `workspace` property to build an image.'


class ProjectAlreadyExistError(MLADException):

    def __init__(self, project_key: str):
        self.project_key = project_key

    def __str__(self):
        return f'Failed to create a project: [{self.project_key}] already exists.'


class InvalidProjectKindError(MLADException):

    def __init__(self, kind: str, command: str = 'train'):
        self.kind = kind
        self.command = command

    def __str__(self):
        return f'Only kind "{self.kind}" is valid for "{self.command}" command.'


class InvalidUpdateOptionError(MLADException):

    def __init__(self, key: str):
        self.key = key

    def __str__(self):
        return f'"{self.key}" cannot be updated. Check the schema for update.'


class NotRunningTrainError(MLADException):

    def __init__(self, key: str):
        self.key = key

    def __str__(self):
        return f'There is no running Train object (project key: {self.key})'


class InvalidFileTypeError(MLADException):

    def __init__(self, type: str):
        self.type = type

    def __str__(self):
        return f'"{self.type}" is unsupported project file type.'


class MountPortAlreadyUsedError(MLADException):

    def __init__(self, port):
        self.port = port

    def __str__(self):
        return f'A registered port [{self.port}] for mount options is already used.'


class MountError(MLADException):
    pass


class PluginUninstalledError(MLADException):
    pass
