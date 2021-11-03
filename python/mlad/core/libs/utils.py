import copy
import uuid
import json
import base64
import jwt
import shortuuid
from typing import Dict

from mlad.core.libs import constants as const
from mlad.core import exceptions


def project_key(workspace):
    return hash(workspace).hex


def get_username(session):
    decoded = jwt.decode(session, "mlad", algorithms="HS256")
    if decoded["user"]:
        return decoded["user"]
    else:
        raise RuntimeError("Session key is invalid.")


def get_repository(base_name, registry=None):
    if registry:
        repository = f"{registry}/{base_name.replace('-', '/', 1)}"
    else:
        repository = f"{base_name.replace('-', '/', 1)}"
    return repository


def merge(source, destination):
    if source:
        for key, value in source.items():
            if isinstance(value, dict):
                # get node or create one
                node = destination.setdefault(key, {})
                merge(value, node)
            else:
                destination[key] = value
    return destination


def update_obj(base, obj):
    # Remove no child branch
    que = [obj]
    while len(que):
        item = que.pop(0)
        if isinstance(item, dict):
            removal_keys = []
            for key in item.keys():
                if key != 'services':
                    if not item[key] is None:
                        que.append(item[key])
                    else:
                        removal_keys.append(key)
            for key in removal_keys:
                del item[key]
    return merge(obj, copy.deepcopy(base))


def generate_unique_id(length=None):
    UUID = uuid.uuid4()
    if length:
        return UUID.hex[:length]
    else:
        return UUID


def hash(body: str):
    import hashlib
    return uuid.UUID(hashlib.md5(body.encode()).hexdigest())


def encode_dict(body):
    return base64.urlsafe_b64encode(json.dumps(body or {}).encode()).decode()


def decode_dict(body):
    return json.loads(base64.urlsafe_b64decode(body.encode()).decode() or "{}")


# Get URL or Socket from CLI
def get_requests_host(cli):
    if cli.api.base_url.startswith('http+docker://localhost'):   # UnixSocket
        for scheme, _ in cli.api.adapters.items():
            if scheme == 'http+docker://':
                return f"http+unix://{_.socket_path.replace('/', '%2F')}"
    elif cli.api.base_url.startswith('https://'):
        return cli.api.base_url
    elif cli.api.base_url.startswith('http://'):
        return cli.api.base_url
    raise exceptions.NotSupportURL


# Change Key Style (ex. task_template -> TaskTemplate)
def change_key_style(dct):
    return dict((k.title().replace('_', ''), v) for k, v in dct.items())


# Manage Project and Network
def base_labels(workspace: str, session: str, manifest: Dict, build: bool = False):
    # workspace = f"{hostname}:{workspace}"
    # Server Side Config 에서 가져올 수 있는건 직접 가져온다.
    username = get_username(session)
    key = project_key(workspace)
    basename = f"{username}-{manifest['name']}-{key[:const.SHORT_LEN]}".lower()

    kind = manifest['kind']
    if not build and kind == 'Deployment':
        deploy_key = shortuuid.uuid()
        key = f"{project_key(workspace)}-{deploy_key}"
        basename = f"{username}-{manifest['name']}-{key[:const.SHORT_LEN]}-" \
                   f"{deploy_key[:const.SHORT_LEN]}".lower()

    version = str(manifest['version']).lower()
    default_image = f"{username}/{manifest['name']}-{key[:const.SHORT_LEN]}:{version}".lower()
    labels = {
        'MLAD.VERSION': '1',
        'MLAD.PROJECT': key,
        'MLAD.PROJECT.WORKSPACE': workspace,
        'MLAD.PROJECT.USERNAME': username,
        'MLAD.PROJECT.API_VERSION': manifest['apiVersion'],
        'MLAD.PROJECT.NAME': manifest['name'].lower(),
        'MLAD.PROJECT.MAINTAINER': manifest['maintainer'],
        'MLAD.PROJECT.VERSION': str(manifest['version']).lower(),
        'MLAD.PROJECT.BASE': basename,
        'MLAD.PROJECT.IMAGE': default_image,
        'MLAD.PROJECT.SESSION': session,
        'MLAD.PROJECT.KIND': manifest['kind']
    }
    return labels
