import sys, os
import requests
from pathlib import Path
from mladcli.libs import utils, docker_controller as docker, interrupt_handler
from mladcli.default import project as default_project

def list(all, tail):
    if all:
        project = None
    else:
        project = utils.get_project(default_project)

    images, dummies = docker.image_list(project['project'] if project else None)

    data = [('ID', 'REGISTRY', 'BUILD USER', 'PROJECT NAME', 'PROJECT AUTHOR', 'VERSION', 'CREATED')]
    for id, repository, tag, head, project_name, author, created in images[:tail]:
        registry, builder, _ = repository.split('/')
        data.append((id, registry, builder, project_name, author, f'[{tag}]' if head else f'{tag}', created))
    utils.print_table(data, 'No have built image.')
    if dummies:
        print(f'This project has {dummies} cached-images. To secure disk spaces by cleaning cache.') 

def search(keyword):
    import urllib3, json
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    config = utils.read_config()
    try:
        images = []
        catalog = json.loads(requests.get(f"http://{config['docker']['registry']}/v2/_catalog", verify=False).text)
        if 'repositories' in catalog:
            repositories = catalog['repositories']
            for repository in repositories:
                tags = json.loads(requests.get(f'http://{config["docker"]["registry"]}/v2/{repository}/tags/list', verify=False).text)
                images += [ f"{config['docker']['registry']}/{tags['name']}:{tag}" for tag in tags['tags'] ] 
            found = [ item for item in filter(None, [image if keyword in image else None for image in images]) ]

            columns = [('REPOSITORY', 'TAG')]
            for item in found:
                repo, tag = item.rsplit(':', 1)
                columns.append((repo, tag))                 
            utils.print_table(columns, 'Cannot find image.', 48)
        else:
            print('No images.', file=sys.stderr)
    except requests.exceptions.ConnectionError as e:
        print(f"Cannot connect to docker registry [{config['docker']['registry']}]", file=sys.stderr)

def remove(ids, force):
    print('Remove project image...')
    result = docker.image_remove(ids, force)
    print('Done.')

def prune(all):
    if not all:
        project = utils.get_project(default_project)

        result = docker.image_prune(project['project'])
        if result:
            print(f'{result} images removed.')
        else:
            print('Already cleared.', file=sys.stderr)
    else:
        result = docker.image_prune()
        if result['ImagesDeleted'] and len(result['ImagesDeleted']):
            for deleted in result['ImagesDeleted']:
                status, value = [ (key, deleted[key]) for key in deleted ][-1]
                print(f'{status:12} {value:32}')
            reclaimed = result['SpaceReclaimed']
            unit = 0
            unit_list = ['B', 'KB', 'MB', 'GB', 'TB' ]
            while reclaimed / 1000. > 1:
                reclaimed /= 1000.
                unit += 1
            print(f'{reclaimed:.2f}{unit_list[unit]} Space Reclaimed.')
        else:
            print('Already cleared.', file=sys.stderr)
        result = docker.image_prune()

