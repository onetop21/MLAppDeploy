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
            project = load(f.read(), Loader=Loader)
        return project or {}
    else:
        return None

def convert_dockerfile(project, workspace):
    config = read_config()
    from MLAppDeploy.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_DEPEND_PIP, DOCKERFILE_DEPEND_APT
    project_name = project['name'].lower()

    envs = [
        DOCKERFILE_ENV.format(KEY='TF_CPP_MIN_LOG_LEVEL', VALUE=3),
        DOCKERFILE_ENV.format(KEY='S3_ENDPOINT', VALUE=config['endpoint']),
        DOCKERFILE_ENV.format(KEY='S3_USE_HTTPS', VALUE=0),
        DOCKERFILE_ENV.format(KEY='AWS_ACCESS_KEY_ID', VALUE=config['accesskey']),
        DOCKERFILE_ENV.format(KEY='AWS_SECRET_ACCESS_KEY_ID', VALUE=config['secretkey']),
    ]
    for key in workspace['env'].keys():
        envs.append(DOCKERFILE_ENV.format(
            KEY=key,
            VALUE=workspace['env'][key]
        ))
    requires = []
    for key in workspace['requires'].keys():
        if key == 'apt':
            requires.append(DOCKERFILE_DEPEND_APT.format(
                SRC=workspace['requires'][key]
            ))
        elif key == 'pip':
            requires.append(DOCKERFILE_DEPEND_PIP.format(
                SRC=workspace['requires'][key]
            )) 

    PROJECT_CONFIG_PATH = '%s/%s'%(CONFIG_PATH, project_name)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'

    os.makedirs(PROJECT_CONFIG_PATH, exist_ok=True)
    with open(DOCKERFILE_FILE, 'w') as f:
        f.write(DOCKERFILE.format(
            BASE=workspace['base'],
            AUTHOR=project['author'],
            ENVS='\n'.join(envs),
            REQUIRES='\n'.join(requires),
            COMMAND='[%s]'%', '.join(
                ['"{}"'.format(item) for item in workspace['command'].split()] + 
                ['"{}"'.format(item) for item in workspace['arguments'].split()]
            ),
        ))

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
    que=[obj]
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

