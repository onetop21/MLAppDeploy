import sys, os
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def module(tagging):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    print('Generating project image...')
    utils.convert_dockerfile(project['project'], project['workspace'])
    image_name = docker.generate_image(project['project'], project['workspace'], tagging)
    if image_name:
        print('Built Image :', image_name)

    print('Update project image to registry...')
    docker.push_image(project['project'])

    print('Done.')

sys.modules[__name__] = module
