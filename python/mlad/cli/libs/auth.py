import os
from functools import lru_cache
from mlad.core.kubernetes.controller import get_current_context
from mlad.core.exception import APIError


@lru_cache(maxsize=None)
def auth_admin():
    try:
        ctx = get_current_context()
    except APIError as e:
        return False
    return True


def get_k8s_config_path():
    config_path = '~/.kube/config'
    env = os.environ.get('KUBECONFIG')
    return config_path if not env else env