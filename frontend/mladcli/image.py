import sys, os
import requests
import docker
from pathlib import Path
from mladcli.libs import utils
from mladcli.libs import docker_controller as ctlr
from mladcli.libs import interrupt_handler
from mladcli.default import project as default_project

def list(all, tail):
    cli = ctlr.get_docker_client()
    if all:
        images = ctlr.get_images(cli)
    else:
        project_key = utils.project_key(utils.get_workspace())
        images = ctlr.get_images(cli, project_key)

    data = [('ID', 'REGISTRY', 'BUILD USER', 'PROJECT NAME', 'PROJECT AUTHOR', 'VERSION', 'CREATED')]
    untagged = 0
    for _ in [ctlr.inspect_image(_) for _ in images[:tail]]:
        if _['short_id'] == _['repository']:
            untagged += 1
            continue
        else:
            registry, builder, __ = _['repository'].split('/')
            row = [
                _['short_id'],
                registry,
                builder,
                _['project_name'],
                _['author'],
                f"[{_['tag']}]" if _['latest'] else f"{_['tag']}",
                _['created']
            ]
            data.append(row)
    utils.print_table(data, 'No have built image.')
    if untagged:
        print(f'This project has {untagged} untagged images. To free disk spaces up by cleaning gabage images.') 

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
    cli = ctlr.get_docker_client()
    try:
        result = ctlr.remove_image(cli, ids, force)
    except docker.errors.ImageNotFound as e:
        print(e, file=sys.stderr)
        result = []
    print('Done.')

def prune(all):
    cli = ctlr.get_docker_client()
    if all:
        result = ctlr.prune_images(cli) 
    else:
        project_key = utils.project_key(utils.get_workspace())
        result = ctlr.prune_images(cli, project_key) 

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

