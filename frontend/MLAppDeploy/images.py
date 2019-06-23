import sys, os
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def module(all, tail):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    images = docker.images(project['project'], all)
    if len(images):
        for image, latest in images[:tail]:
            print(' %s %s' % ('*' if latest else ' ', image))
    else:
        print('No have built image.')

sys.modules[__name__] = module
