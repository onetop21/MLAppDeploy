import sys, os
from pathlib import Path
import MLAppDeploy.libs.utils as utils
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default
from MLAppDeploy.Format import PROJECT

def init(name, version, author):
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

def list():
    docker.running_projects()

def status(all):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)
    
    docker.show_status(project['project'], project['services'], all)

def build(tagging):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    print('Generating project image...')
    utils.convert_dockerfile(project['project'], project['workspace'])
    image_name = docker.image_build(project['project'], project['workspace'], tagging)
    if image_name:
        print('Built Image :', image_name)

    print('Update project image to registry...')
    docker.image_push(project['project'])

    print('Done.')

def test(_build):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    if _build: build(False)

    print('Deploying test container image to local...')
    project_name = docker.images_up(project['project'], project['services'], False)
    if project_name:
        docker.show_logs(project['project'], 'all', True, [], False)
    docker.images_down(project['project'], False)

    #utils.networks.prune()

    print('Done.')

def up(image):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)

    print('Deploying services to cluster...')
    project_name = docker.images_up(project['project'], project['services'], True)
    if not project_name: docker.images_down(project['project'], True)

    #utils.networks.prune()

    print('Done.')

def down():
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    docker.images_down(project['project'], True)

    print('Done.')

def logs(tail, follow):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)
    
    docker.show_logs(project['project'], tail, follow, [], True)

def scale(scales):
    scale_spec = dict([ scale.split('=') for scale in scales ])

    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)
    
    docker.scale_service(project['project'], scale_spec)


