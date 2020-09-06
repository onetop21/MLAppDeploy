import sys, os
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def module(no_build):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    print('Generating container image for test...')
    utils.convert_dockerfile(project['project'], project['workspace'])
    project_name, image_name = docker.generate_image(project['project'], project['workspace'], True)

    print('Deploying test container image to local...')
    docker.start_project(project_name, image_name, project['services'], True)

    docker.show_project_logs(project_name, True)

    #utils.networks.prune()

    docker.stop_project(project_name, True)

    print('Done.')

sys.modules[__name__] = module
