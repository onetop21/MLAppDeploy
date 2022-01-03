from functools import lru_cache
from mlad.core.kubernetes.controller import get_current_context
from mlad.core.exceptions import APIError


@lru_cache(maxsize=None)
def auth_admin():
    try:
        get_current_context()
    except APIError:
        return False
    return True
