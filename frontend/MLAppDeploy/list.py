import sys, os
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def module():
    docker.running_projects()

sys.modules[__name__] = module
