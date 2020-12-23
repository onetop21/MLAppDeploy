import sys, os
from pathlib import Path
from mladcli.libs import utils, docker_controller as docker, interrupt_handler
from mladcli.default import project as default_project
from mladcli.Format import PROJECT

def init(name, version, author):
    if utils.read_project():
        print('Already generated project file.', file=sys.stderr)
        sys.exit(1)

    if not name: name = input('Project Name : ')
    #if not version: version = input('Project Version : ')
    #if not author: author = input('Project Author : ')

    with open(utils.PROJECT_FILE, 'w') as f:
        f.write(PROJECT.format(
            NAME=name,
            VERSION=version,
            AUTHOR=author,
        ))

def list():
    data = docker.running_projects()

    columns = [('PROJECT', 'USERNAME', 'IMAGE', 'SERVICES', 'TASKS')]
    for project in data:
        running_tasks = f"{data[project]['tasks']}/{data[project]['replicas']}"
        columns.append((project, data[project]['username'], data[project]['image'], data[project]['services'], f"{running_tasks:>5}"))
    utils.print_table(columns, 'Cannot find running project.', 48)

def status(all):
    project = utils.get_project(default_project)
    
    task_info = docker.show_status(project['project'], project['services'] or {}, all)
    columns = [('ID', 'USERNAME', 'PROJECT', 'SERVICE', 'SLOT', 'NODE', 'DESIRED STATE', 'CURRENT STATE', 'ERROR', 'UPTIME', 'PORTS')]
    for id, name, username, service, slot, node, desired_state, current_state, error, uptime, ports in task_info:
        columns.append((id, username, name, service, slot, node, desired_state, current_state, error, uptime, ports))
    utils.print_table(columns, 'Project is not running.')

def build(tagging, verbose):
    project = utils.get_project(default_project)

    print('Generating project image...')
    utils.convert_dockerfile(project['project'], project['workspace'])
    image_name = docker.image_build(project['project'], project['workspace'], tagging, verbose)
    if image_name:
        print('Built Image :', image_name)

    print('Update project image to registry...')
    docker.image_push(project['project'])

    print('Done.')

def test(_build):
    project = utils.get_project(default_project)

    if _build: build(False)

    print('Deploying test container image to local...')
    project_name = docker.images_up(project['project'], project['services'] or {}, False)
    if project_name:
        docker.show_logs(project['project'], 'all', True, False, [], False)
    docker.images_down(project['project'], False)

    #utils.networks.prune()

    print('Done.')

def up(services):
    project = utils.get_project(default_project)

    print('Deploying services to cluster...')
    if services:
        up_services = {}
        for name in services:
            if name in project['services']:
                up_services[name] = project['services'][name]
            else:
                print(f'Cannot find service[{name}] in mlad-project.yaml.', file=sys.stderr)
                sys.exit(1)
        project['project']['partial'] = True
    else:
        up_services = project['services'] or {}
        project['project']['partial'] = False
            
    project_name = docker.images_up(project['project'], up_services, True)
    if not project_name: docker.images_down(project['project'], True)
    #utils.networks.prune()
    print('Done.')

def down(services):
    project = utils.get_project(default_project)

    if services:
        down_services = {}
        for name in services:
            if name in project['services']:
                down_services[name] = project['services'][name]
            else:
                print(f'Cannot find service[{name}] in mlad-project.yaml.', file=sys.stderr)
                sys.exit(1)
        project['project']['partial'] = True
    else:
        down_services = project['services'] or {}
        project['project']['partial'] = False
 
    docker.images_down(project['project'], down_services, True)
    print('Done.')

def logs(tail, follow, timestamps, targets):
    project = utils.get_project(default_project)
    docker.show_logs(project['project'], tail, follow, timestamps, targets, True)

def scale(scales):
    scale_spec = dict([ scale.split('=') for scale in scales ])
    project = utils.get_project(default_project)
    docker.scale_service(project['project'], scale_spec)


