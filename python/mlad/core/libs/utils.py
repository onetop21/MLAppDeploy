import copy
import uuid
import json
import base64
import jwt

from mlad.core import exceptions


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
                if key != 'apps':
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
