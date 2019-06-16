import sys, os
import MLAppDeploy.utils as utils
from MLAppDeploy.Format import PROJECT

def module(name, version, author):
    if utils.read_project():
        print('Already generated project file.', file=sys.stderr)
        sys.exit(1)

    if not name: name = input('Project Name : ')
    if not version: version = input('Project Version : ')
    if not author: author = input('Project Author : ')

    with open(utils.PROJECT_FILE, 'w') as f:
        f.write(PROJECT.format(
            NAME=name,
            VERSION=version,
            AUTHOR=author,
        ))

sys.modules[__name__] = module
