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

def generate_empty_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_PATH, exist_ok=True)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            f.write('')

def getProjectConfigPath(project):
    config = read_config()
    return '%s/%s/%s'%(CONFIG_PATH, config['account']['username'], project['name'].lower())

def getProjectName(project):
    config = read_config()
    return '{USERNAME}_{PROJECT}'.format(USERNAME=config['account']['username'], PROJECT=project['name'].lower())

def getRepository(project):
    config = read_config()
    repository = '{REPO}/{OWNER}/{NAME}'.format(
        REPO=config['docker']['registry'],
        OWNER=config['account']['username'],
        NAME=project['name'].lower(),
    )
    return repository

def read_config():
    try:
        with open(CONFIG_FILE) as f:
            config = load(f.read(), Loader=Loader)
        return config or {}
    except FileNotFoundError as e:
        print('Need to initialize configuration before.\nTry to run "mlad config init"', file=sys.stderr)
        sys.exit(1)

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

def get_project(default):
    project = read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    return default.project(project)

def print_table(data, no_data_msg=None, max_width=32):
    widths = [max(_) for _ in zip(*[[min(len(str(value)), max_width) for value in datum] for datum in data])]
    format = '  '.join([('{:%d}' % _) for _ in widths])
    titled = False
    for datum in data:
        if not titled:
            print(format.format(*datum).upper())
            titled = True
        else:
            print(format.format(*datum))
    if len(data) < 2:
        print(no_data_msg, file=sys.stderr)

def convert_dockerfile(project, workspace):
    config = read_config()
    from MLAppDeploy.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT

    envs = [
        #DOCKERFILE_ENV.format(KEY='TF_CPP_MIN_LOG_LEVEL', VALUE=3),
        #DOCKERFILE_ENV.format(KEY='S3_ENDPOINT', VALUE=config['s3']['endpoint']),
        #DOCKERFILE_ENV.format(KEY='S3_USE_HTTPS', VALUE=0),
        #DOCKERFILE_ENV.format(KEY='AWS_ACCESS_KEY_ID', VALUE=config['s3']['accesskey']),
        #DOCKERFILE_ENV.format(KEY='AWS_SECRET_ACCESS_KEY', VALUE=config['s3']['secretkey']),
    ]
    for key in workspace['env'].keys():
        envs.append(DOCKERFILE_ENV.format(
            KEY=key,
            VALUE=workspace['env'][key]
        ))
    requires = []
    for key in workspace['requires'].keys():
        if key == 'apt':
            requires.append(DOCKERFILE_REQ_APT.format(
                SRC=workspace['requires'][key]
            ))
        elif key == 'pip':
            requires.append(DOCKERFILE_REQ_PIP.format(
                SRC=workspace['requires'][key]
            )) 

    PROJECT_CONFIG_PATH = getProjectConfigPath(project)
    DOCKERFILE_FILE = PROJECT_CONFIG_PATH + '/Dockerfile'

    os.makedirs(PROJECT_CONFIG_PATH, exist_ok=True)
    with open(DOCKERFILE_FILE, 'w') as f:
        f.write(DOCKERFILE.format(
            BASE=workspace['base'],
            AUTHOR=project['author'],
            ENVS='\n'.join(envs),
            PRESCRIPTS=';'.join(workspace['prescripts']) if len(workspace['prescripts']) else "echo .",
            REQUIRES='\n'.join(requires),
            POSTSCRIPTS=';'.join(workspace['postscripts']) if len(workspace['postscripts']) else "echo .",
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

def is_wsl2():
   return 'microsoft-standard' in os.uname()[2]
