import sys
import os
import io
import tarfile
import json
import base64
import urllib3
import requests
import docker
from pathlib import Path
from mlad.core.default import project as default_project
from mlad.core.default import plugin as default_plugin
from mlad.core.docker import controller as ctlr
from mlad.core.libs import utils as core_utils
from mlad.cli import config as config_core
from mlad.cli.libs import utils
from mlad.cli.libs import interrupt_handler
from mlad.cli.Format import PROJECT
from mlad.cli.Format import DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT

def list(all, plugin, tail, no_trunc):
    cli = ctlr.get_api_client()
    if all:
        images = ctlr.get_images(cli, extra_labels=['MLAD.PROJECT.TYPE=project'])# + \
        #         ctlr.get_images(cli, extra_labels=['MLAD.PROJECT.TYPE=plugin'])
    elif plugin:
        images = ctlr.get_images(cli, extra_labels=['MLAD.PROJECT.TYPE=plugin'])
    else:
        project_key = utils.project_key(utils.get_workspace())
        images = ctlr.get_images(cli, project_key)

    data = [('ID', 'BUILD USER', 'TYPE', 'NAME', 'VERSION', 'MAINTAINER', 'CREATED')]
    if all:
        data = [('ID', 'BUILD USER', 'TYPE', 'NAME', 'VERSION', 'MAINTAINER', 'CREATED', 'WORKSPACE')]

    untagged = 0
    for inspect in [ctlr.inspect_image(_) for _ in images[:tail]]:
        if len(inspect['tags']) == 0:
            untagged += 1
        else:
            row = [
                inspect['short_id'],
                inspect['username'],
                inspect['type'].upper(),
                inspect['project_name'],
                f"[{inspect['tag']}]" if inspect['latest'] else f"{inspect['tag']}",
                inspect['maintainer'],
                inspect['created']
            ]
            if all:
                row.append(inspect['workspace'])
            data.append(row)
    utils.print_table(*([data, 'No have built image.'] + ([0] if no_trunc else [])))
    if untagged:
        print(f'This project has {untagged} untagged images. To free disk spaces up by cleaning gabage images.') 

def build(quiet, plugin, no_cache, pull):
    config = config_core.get()
    cli = ctlr.get_api_client()
    
    manifest_type = 'plugin' if plugin else 'project'
    default = default_plugin if plugin else default_project
    manifest = utils.get_manifest(manifest_type, default)

    # Generate Base Labels
    base_labels = core_utils.base_labels(
        utils.get_workspace(), 
        config.mlad.session,
        manifest[manifest_type], 
        manifest_type
    )
    project_key = base_labels['MLAD.PROJECT']

    # Append service manfest using label.
    if plugin:
        base_labels['MLAD.PROJECT.PLUGIN_MANIFEST']=base64.urlsafe_b64encode(json.dumps(manifest['service']).encode()).decode()

    # Prepare Latest Image
    latest_image = None
    images = ctlr.get_images(cli, extra_labels=[f'MLAD.PROJECT.TYPE={manifest_type}'])
    if len(images):
        latest_image = sorted(filter(None, [ image if tag.endswith('latest') else None for image in images for tag in image.tags ]), key=lambda x: str(x))
        if latest_image and len(latest_image): latest_image = latest_image[0]
    image_version = f"{base_labels['MLAD.PROJECT.VERSION']}"

    print(f'Generating {manifest_type} image...')

    if manifest['workspace'] != default({})['workspace']:
        # Prepare workspace data from manifest file
        envs = []
        for key in manifest['workspace']['env'].keys():
            envs.append(DOCKERFILE_ENV.format(
                KEY=key,
                VALUE=manifest['workspace']['env'][key]
            ))
        requires = []
        for key in manifest['workspace']['requires'].keys():
            if key == 'apt':
                requires.append(DOCKERFILE_REQ_APT.format(
                    SRC=manifest['workspace']['requires'][key]
                ))
            elif key == 'pip':
                requires.append(DOCKERFILE_REQ_PIP.format(
                    SRC=manifest['workspace']['requires'][key]
                )) 

        # Dockerfile to memory
        dockerfile = DOCKERFILE.format(
            BASE=manifest['workspace']['base'],
            MAINTAINER=manifest[manifest_type]['maintainer'],
            ENVS='\n'.join(envs),
            PRESCRIPTS=';'.join(manifest['workspace']['prescripts']) if len(manifest['workspace']['prescripts']) else "echo .",
            REQUIRES='\n'.join(requires),
            POSTSCRIPTS=';'.join(manifest['workspace']['postscripts']) if len(manifest['workspace']['postscripts']) else "echo .",
            COMMAND='[{}]'.format(', '.join(
                [f'"{item}"' for item in manifest['workspace']['command'].split()] + 
                [f'"{item}"' for item in manifest['workspace']['arguments'].split()]
            )),
        )

        tarbytes = io.BytesIO()
        dockerfile_info = tarfile.TarInfo('.dockerfile')
        dockerfile_info.size = len(dockerfile)
        with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
            for name, arcname in utils.arcfiles(manifest[manifest_type]['workdir'], manifest['workspace']['ignore']):
                tar.add(name, arcname)
            tar.addfile(dockerfile_info, io.BytesIO(dockerfile.encode()))
        tarbytes.seek(0)

        # Build Image
        build_output = ctlr.build_image(cli, base_labels, tarbytes, dockerfile_info.name, no_cache, pull, stream=True)

    else:
        dockerfile = f"FROM {manifest['service']['image']}\nMAINTAINER {manifest[manifest_type]['maintainer']}"

        tarbytes = io.BytesIO()
        dockerfile_info = tarfile.TarInfo('.dockerfile')
        dockerfile_info.size = len(dockerfile)
        with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
            tar.addfile(dockerfile_info, io.BytesIO(dockerfile.encode()))
        tarbytes.seek(0)

        # Build Image
        build_output = ctlr.build_image(cli, base_labels, tarbytes, dockerfile_info.name, no_cache, pull, stream=True)

    # Print build output
    for _ in build_output:
        if 'error' in _:
            sys.stderr.write(f"{_['error']}\n")
            sys.exit(1)
        elif 'stream' in _:
            if not quiet:
                sys.stdout.write(_['stream'])

    image = ctlr.get_image(cli, base_labels['MLAD.PROJECT.IMAGE'])

    #print(docker.auth.resolve_repository_name(base_labels['MLAD.PROJECT.IMAGE']))
    repository = base_labels['MLAD.PROJECT.IMAGE']
    # Check updated
    if latest_image != image:
        if latest_image and len(latest_image.tags) < 2 and latest_image.tags[-1].endswith(':latest'):
            latest_image.tag('remove')
            cli.images.remove('remove')
        print(f"Built Image: {repository}")
    else:
        print(f'Already built {manifest_type} to image.', file=sys.stderr)

    #updated = False
    #if latest_image != image:
    #    image.tag(repository)
    #    updated = True
    #    if latest_image and len(latest_image.tags) < 2 and latest_image.tags[-1].endswith(':latest'):
    #        latest_image.tag('remove')
    #        cli.images.remove('remove')
    #else:
    #    if len(latest_image.tags) < 2:
    #        image.tag(repository, tag=image_version)
    #        updated = True
    #    else:
    #        print(f'Already built {manifest_type} to image.', file=sys.stderr)

    #if updated:
    #    #print(f"Built Image: {'/'.join(repository.split('/')[1:])}:{image_version}")
    #    print(f"Built Image: {repository}")

    print('Done.')

def search(keyword):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    config = config_core.get()
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
    cli = ctlr.get_api_client()
    try:
        result = ctlr.remove_image(cli, ids, force)
    except docker.errors.ImageNotFound as e:
        print(e, file=sys.stderr)
        result = []
    print('Done.')

def prune(all):
    cli = ctlr.get_api_client()
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
