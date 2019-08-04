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
    data = docker.running_projects()

    columns = [('PROJECT', 'USERNAME', 'IMAGE', 'SERVICES')]
    for project in data:
        columns.append((project, data[project]['username'], data[project]['image'], data[project]['services']))
    utils.print_table(columns, 'Cannot find running project.', 48)

def status(all):
    project = utils.get_project(default)
    
    task_info = docker.show_status(project['project'], project['services'] or {}, all)
    columns = [('ID', 'USERNAME', 'PROJECT', 'SERVICE', 'NODE', 'DESIRED STATE', 'CURRENT STATE', 'ERROR')]
    for id, name, username, service, node, desired_state, current_state, error in task_info:
        columns.append((id, username, name, service, node, desired_state, current_state, error))
    utils.print_table(columns, 'Project is not running.')

def build(tagging):
    project = utils.get_project(default)

    print('Generating project image...')
    utils.convert_dockerfile(project['project'], project['workspace'])
    image_name = docker.image_build(project['project'], project['workspace'], tagging)
    if image_name:
        print('Built Image :', image_name)

    print('Update project image to registry...')
    docker.image_push(project['project'])

    print('Done.')

def test(_build):
    project = utils.get_project(default)

    if _build: build(False)

    print('Deploying test container image to local...')
    project_name = docker.images_up(project['project'], project['services'] or {}, False)
    if project_name:
        docker.show_logs(project['project'], 'all', True, [], False)
    docker.images_down(project['project'], False)

    #utils.networks.prune()

    print('Done.')

def up(image):
    project = utils.get_project(default)

    print('Deploying services to cluster...')
    project_name = docker.images_up(project['project'], project['services'] or {}, True)
    if not project_name: docker.images_down(project['project'], True)
    #utils.networks.prune()
    print('Done.')

def down():
    project = utils.get_project(default)
    docker.images_down(project['project'], True)
    print('Done.')

def logs(tail, follow, services):
    project = utils.get_project(default)
    docker.show_logs(project['project'], tail, follow, services, True)

def scale(scales):
    scale_spec = dict([ scale.split('=') for scale in scales ])
    project = utils.get_project(idefault)
    docker.scale_service(project['project'], scale_spec)


