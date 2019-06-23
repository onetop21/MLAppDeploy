import sys, os
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def module(build, as_test, image):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    if build:
        print('Generating project image...')
        utils.convert_dockerfile(project['project'], project['workspace'])
        docker.generate_image(project['project'], project['workspace'])

        print('Update project image to registry...')
        docker.push_image(project['project'])

    if as_test:
        print('Deploying test container image to local...')
        project_name = docker.images_up(project['project'], project['services'], False)
        docker.show_logs(project['project'], 'all', True, False)
        docker.images_down(project['project'], False)
    else:
        print('Deploying services to cluster...')
        project_name = docker.images_up(project['project'], project['services'], True)

    #utils.networks.prune()

    print('Done.')

sys.modules[__name__] = module
