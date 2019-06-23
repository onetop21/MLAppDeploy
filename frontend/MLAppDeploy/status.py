import sys, os
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def module():
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)
    
    docker.show_status(project['project'], project['services'])

sys.modules[__name__] = module
