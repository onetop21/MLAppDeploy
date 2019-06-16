import sys, os, copy
from pathlib import Path
from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError as e:
    from yaml import Loader, Dumper

HOME = str(Path.home())
CONFIG_PATH = HOME + '/.mlad'
CONFIG_FILE = HOME + '/.mlad/config.yml'
PROJECT_PATH = os.getcwd()
PROJECT_FILE = os.getcwd() + '/mlad-project.yml'

def generate_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_PATH, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write('')

def read_config():
    with open(CONFIG_FILE) as f:
        config = load(f.read(), Loader=Loader)
    return config or {}

def write_config(config):
    with open(CONFIG_FILE, 'w') as f:
        f.write(dump(config, default_flow_style=False, Dumper=Dumper))

def read_project():
    if os.path.exists(PROJECT_FILE):
        with open(PROJECT_FILE) as f:
            config = load(f.read(), Loader=Loader)
        return config or {}
    else:
        return None

def convert_dockerfile(project, workspace):
    from MLAppDeploy.Foramt import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_DEPEND_PIP, DOCKERFILE_DEPEND_APT
    project_name = project['name'].lower()
    image_name = '{OWNER}'
    pass

def convert_composefile(project, services):
    pass

def update_obj(base, obj):
    # Remove no child branch
    que=[obj]
    while len(que):
        item = que.pop(0)
        if isinstance(item, dict):
            removal_keys = []
            for key in item.keys():
                if not item[key] is None:
                    que.append(item[key])
                else:
                    removal_keys.append(key)
            for key in removal_keys:
                del item[key]
    new = copy.deepcopy(base)
    new.update(obj)
    return new


