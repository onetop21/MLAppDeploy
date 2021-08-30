import sys
import io
import tarfile
import json
import urllib3
import requests
import docker
from mlad.core.docker import controller as ctlr
from mlad.core.libs import utils as core_utils
from mlad.cli import config as config_core
from mlad.cli.libs import utils
from mlad.cli.Format import (
    DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT,
    DOCKERFILE_REQ_ADD, DOCKERFILE_REQ_RUN, DOCKERFILE_REQ_APK, DOCKERFILE_REQ_YUM
)

PREP_KEY_TO_TEMPLATE = {
    'run': DOCKERFILE_REQ_RUN,
    'add': DOCKERFILE_REQ_ADD,
    'apt': DOCKERFILE_REQ_APT,
    'pip': DOCKERFILE_REQ_PIP,
    'apk': DOCKERFILE_REQ_APK,
    'yum': DOCKERFILE_REQ_YUM
}


def list(all, plugin, tail, no_trunc):
    cli = ctlr.get_api_client()
    if all:
        images = ctlr.get_images(cli, extra_labels=['MLAD.PROJECT.TYPE=project'])
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
        print(f'This project has {untagged} untagged images.'
              'To free disk spaces up by cleaning gabage images.')


def build(quiet: bool, no_cache: bool, pull: bool):
    config = config_core.get()
    cli = ctlr.get_api_client()
    manifest = utils.get_manifest()

    # Generate Base Labels
    workspace_key = utils.get_workspace()
    base_labels = core_utils.base_labels(workspace_key, config.session, manifest)

    # Prepare Latest Image
    latest_image = None
    images = ctlr.get_images(cli)
    if len(images) > 0:
        latest_images = sorted([
            image
            for image in images for tag in image.tags
            if tag.endswith('latest')
        ], key=lambda x: str(x))
        if len(latest_images) > 0:
            latest_image = latest_images[0]

    workspace = manifest['workspace']
    # For the workspace kind
    if workspace['kind'] == 'Workspace':
        payload = _obtain_workspace_payload(workspace, manifest['maintainer'])
    # For the dockerfile kind
    else:
        if 'dockerfile' in workspace:
            with open(workspace['dockerfile'], 'r') as dockerfile:
                payload = dockerfile.read()
        else:
            payload = workspace['script']

    tarbytes = io.BytesIO()
    dockerfile_info = tarfile.TarInfo('.dockerfile')
    dockerfile_info.size = len(payload)
    with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
        for name, arcname in utils.arcfiles(manifest['workdir'], workspace['ignores']):
            tar.add(name, arcname)
        tar.addfile(dockerfile_info, io.BytesIO(payload.encode()))
    tarbytes.seek(0)

    # Build Image
    build_output = ctlr.build_image(cli, base_labels, tarbytes, dockerfile_info.name,
                                    no_cache, pull, stream=True)

    # Print build output
    for _ in build_output:
        if 'error' in _:
            sys.stderr.write(f"{_['error']}\n")
            sys.exit(1)
        elif 'stream' in _:
            if not quiet:
                sys.stdout.write(_['stream'])

    image = ctlr.get_image(cli, base_labels['MLAD.PROJECT.IMAGE'])

    repository = base_labels['MLAD.PROJECT.IMAGE']

    # Check updated
    if latest_image != image:
        if latest_image is not None and len(latest_image.tags) < 2 \
                and latest_image.tags[-1].endswith(':latest'):
            latest_image.tag('remove')
            cli.images.remove('remove')
        print(f"Built Image: {repository}")
    else:
        print('The same image has been build before', file=sys.stderr)

    print('Done.')
    return image


def _obtain_workspace_payload(workspace, maintainer):
    envs = [DOCKERFILE_ENV.format(KEY=k, VALUE=v) for k, v in workspace['env'].items()]
    preps = workspace['preps']
    prep_docker_formats = []
    for prep in preps:
        key = tuple(prep.keys())[0]
        template = PREP_KEY_TO_TEMPLATE[key]
        prep_docker_formats.append(template.format(SRC=prep[key]))

    commands = [f'"{item}"' for item in workspace['command'].split()] + \
        [f'"{item}"' for item in workspace['arguments'].split()]

    return DOCKERFILE.format(
        BASE=workspace['base'],
        MAINTAINER=maintainer,
        ENVS='\n'.join(envs),
        PREPS='\n'.join(prep_docker_formats),
        SCRIPT=';'.join(workspace['script']) if len(workspace['script']) else "echo .",
        COMMAND=f'[{", ".join(commands)}]',
    )


def search(keyword):
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    config = config_core.get()
    try:
        images = []
        registry_address = config.docker.registry.address
        catalog = json.loads(requests.get(f"http://{registry_address}/v2/_catalog", verify=False).text)
        if 'repositories' in catalog:
            repositories = catalog['repositories']
            for repository in repositories:
                tags = json.loads(requests.get(f'http://{registry_address}/v2/{repository}/tags/list', verify=False).text)
                images += [ f"{config['docker']['registry']}/{tags['name']}:{tag}" for tag in tags['tags'] ] 
            found = [ item for item in filter(None, [image if keyword in image else None for image in images]) ]

            columns = [('REPOSITORY', 'TAG')]
            for item in found:
                repo, tag = item.rsplit(':', 1)
                columns.append((repo, tag))
            utils.print_table(columns, 'Cannot find image.', 48)
        else:
            print('No images.', file=sys.stderr)
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to docker registry [{config['docker']['registry']}]", file=sys.stderr)


def remove(ids, force):
    print('Remove project image...')
    cli = ctlr.get_api_client()
    try:
        ctlr.remove_image(cli, ids, force)
    except docker.errors.ImageNotFound as e:
        print(e, file=sys.stderr)
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
            status, value = [(key, deleted[key]) for key in deleted][-1]
            print(f'{status:12} {value:32}')
        reclaimed = result['SpaceReclaimed']
        unit = 0
        unit_list = ['B', 'KB', 'MB', 'GB', 'TB']
        while reclaimed / 1000. > 1:
            reclaimed /= 1000.
            unit += 1
        print(f'{reclaimed:.2f}{unit_list[unit]} Space Reclaimed.')
    else:
        print('Already cleared.', file=sys.stderr)
