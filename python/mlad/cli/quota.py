from mlad.api import API
from mlad.cli.exceptions import InvalidMemoryFormatError


def set_default(cpu: float, gpu: int, mem: str):
    _validate_mem(mem)
    API.quota.set_default(cpu, gpu, mem)


def set_quota(session_key: str, cpu: float, gpu: int, mem: str):
    _validate_mem(mem)
    API.quota.set_quota(session_key, cpu, gpu, mem)


def _validate_mem(mem: str) -> None:
    suffixes = ['K', 'M', 'G', 'Ki', 'Mi', 'Gi']
    if not any(map(lambda x: mem.endswith(x), suffixes)):
        raise InvalidMemoryFormatError
