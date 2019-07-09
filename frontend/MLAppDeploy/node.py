import sys, os
import requests
from pathlib import Path
from MLAppDeploy.libs import utils, docker_controller as docker, interrupt_handler
import MLAppDeploy.default as default

def list(all, tail):
    if all:
        project = None
    else:
        project = utils.read_project()
        if not project:
            print('Need to generate project file before.', file=sys.stderr)
            print('$ %s --help' % sys.argv[0], file=sys.stderr)
            sys.exit(1)

        project = default.project(project)

    images = docker.image_list(project['project'] if project else None)

    print('{:12} {:24} {:16} {:16} {:16} {:10} {:16}'.format('ID', 'REGISTRY', 'BUILD USER', 'PROJECT NAME', 'PROJECT AUTHOR', 'VERSION', 'CREATED'))
    if len(images):
        for id, repository, tag, head, project_name, author, created in images[:tail]:
            registry, builder, _ = repository.split('/')
            print('{:12} {:24} {:16} {:16} {:16} {:10} {:16}'.format(id, registry, builder, project_name, author, ('[{}]' if head else '{}').format(tag), created))
    else:
        print('No have built image.')

def search(keyword):
    import urllib3, json
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    config = utils.read_config()
    try:
        images = []
        catalog = json.loads(requests.get('https://%s/v2/_catalog' % config['docker']['registry'], verify=False).text)
        if 'repositories' in catalog:
            repositories = catalog['repositories']
            for repository in repositories:
                tags = json.loads(requests.get('https://%s/v2/%s/tags/list' % (config['docker']['registry'], repository), verify=False).text)
                images += [ '%s/%s:%s' % (config['docker']['registry'], tags['name'], tag) for tag in tags['tags'] ] 
            found = [ item for item in filter(None, [image if keyword in image else None for image in images]) ]
            if len(found):
                print('{:48} {:10}'.format('REPOSITORY', 'TAG'))                 
                for item in found:
                    repo, tag = item.rsplit(':', 1)
                    print('{:48} {:10}'.format(repo, tag))                 
            else:
                print('Cannot find image.', file=sys.stderr)
        else:
            print('No images.', file=sys.stderr)
    except requests.exceptions.ConnectionError as e:
        print('Cannot connect to docker registry [%s]' % config['docker']['registry'], file=sys.stderr)

def remove(ids, force):
    print('Remove project image...')
    result = docker.image_remove(ids, force)
    print(result)
    print('Done.')

def prune(strong):
    project = utils.read_project()
    if not project:
        print('Need to generate project file before.', file=sys.stderr)
        print('$ %s --help' % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    project = default.project(project)
    result = docker.image_prune(project['project'], strong)
    if result['ImagesDeleted'] and len(result['ImagesDeleted']):
        for deleted in result['ImagesDeleted']:
            print(deleted)
            status, value = list(deleted.items())[0] 
            print('{:12} {:32}'.format(status, value))
        reclamed = result['SpaceReclamed']
        unit = 0
        unit_list = ['B', 'KB', 'MB', 'GB', 'TB' ]
        while reclamed / 1000 > 1:
            reclamed /= 1000
            unit += 1
        print('%.1d%s Space Reclamed.' % (reclamed, unit_list[unit]))
    else:
        print('Already cleared.', file=sys.stderr)

