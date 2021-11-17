import sys
import io
import tarfile

from typing import Optional

from mlad.cli import config as config_core
from mlad.cli.validator import validators
from mlad.cli.libs import utils
from mlad.cli.Format import (
    DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT,
    DOCKERFILE_REQ_ADD, DOCKERFILE_REQ_RUN, DOCKERFILE_REQ_APK, DOCKERFILE_REQ_YUM
)

from mlad.core.docker import controller2 as ctlr
from mlad.core.libs import utils as core_utils
from mlad.core.default import project as default_project

PREP_KEY_TO_TEMPLATE = {
    'run': DOCKERFILE_REQ_RUN,
    'add': DOCKERFILE_REQ_ADD,
    'apt': DOCKERFILE_REQ_APT,
    'pip': DOCKERFILE_REQ_PIP,
    'apk': DOCKERFILE_REQ_APK,
    'yum': DOCKERFILE_REQ_YUM
}


def list(all, tail):
    if all:
        images = ctlr.get_images()
    else:
        project_key = utils.workspace_key()
        images = ctlr.get_images(project_key=project_key)

    data = [('ID', 'BUILD USER', 'NAME', 'TAG', 'MAINTAINER', 'CREATED')]
    if all:
        data = [('ID', 'BUILD USER', 'NAME', 'TAG', 'MAINTAINER', 'CREATED', 'WORKSPACE')]

    untagged = 0
    for inspect in [ctlr.inspect_image(image) for image in images[:tail]]:
        if len(inspect['tags']) == 0:
            untagged += 1
        else:
            row = [
                inspect['short_id'],
                inspect['username'],
                inspect['project_name'],
                inspect['tag'],
                inspect['maintainer'],
                inspect['created']
            ]
            if all:
                row.append(inspect['workspace'])
            data.append(row)
    utils.print_table(data, 'There is no built image.', 0)
    if untagged:
        print(f'This project has {untagged} untagged images. '
              'Delete untagged images to free the disk space. '
              'Use command `mlad image prune`')


def build(file: Optional[str], quiet: bool, no_cache: bool, pull: bool):
    utils.process_file(file)
    config = config_core.get()
    project = utils.get_project(default_project)
    project = validators.validate(project)

    # Generate Base Labels
    workspace = utils.get_workspace()
    registry_address = utils.get_registry_address(config)
    base_labels = core_utils.base_labels(
        workspace, config.session, project, registry_address, build=True)
    project_key = base_labels['MLAD.PROJECT']
    version = base_labels['MLAD.PROJECT.VERSION']
    repository = base_labels['MLAD.PROJECT.IMAGE']

    workspace = project['workspace']
    # For the workspace kind
    if workspace['kind'] == 'Workspace':
        payload = _obtain_workspace_payload(workspace, project['maintainer'])
    # For the dockerfile kind
    else:
        if 'dockerfile' in workspace:
            with open(workspace['dockerfile'], 'r') as dockerfile:
                payload = dockerfile.read()
        else:
            payload = workspace['buildscript']

    tarbytes = io.BytesIO()
    dockerfile_info = tarfile.TarInfo('.dockerfile')
    dockerfile_info.size = len(payload)
    with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
        for name, arcname in utils.arcfiles(project['workdir'], workspace['ignores']):
            tar.add(name, arcname)
        tar.addfile(dockerfile_info, io.BytesIO(payload.encode()))
    tarbytes.seek(0)

    # Build Image
    build_output = ctlr.build_image(base_labels, tarbytes, dockerfile_info.name,
                                    no_cache, pull, stream=True)

    # Print build output
    for _ in build_output:
        if 'error' in _:
            sys.stderr.write(f"{_['error']}\n")
            sys.exit(1)
        elif 'stream' in _:
            if not quiet:
                sys.stdout.write(_['stream'])

    image = ctlr.get_image(repository)

    # Prepare the previous images
    images = ctlr.get_images(project_key=project_key)
    prev_images = [
        im
        for im in images
        for tag in im.tags if tag.endswith(version)
    ]
    # Remove the previous images with different ids
    for prev_image in prev_images:
        if prev_image != image:
            prev_image.tag('remove')
            ctlr.remove_image(['remove'])
    yield f'Built Image: {repository}'

    # Push image
    yield f'Upload the image to the registry [{registry_address}]...'
    for line in ctlr.push_image(repository):
        yield line

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
        [f'"{item}"' for item in workspace['args'].split()]

    return DOCKERFILE.format(
        BASE=workspace['base'],
        MAINTAINER=maintainer,
        ENVS='\n'.join(envs),
        PREPS='\n'.join(prep_docker_formats),
        SCRIPT=';'.join(workspace['script']) if len(workspace['script']) else "echo .",
        COMMAND=f'[{", ".join(commands)}]',
    )


def remove(ids, force):
    ctlr.remove_image(ids, force)


def prune(all):
    if all:
        result = ctlr.prune_images()
    else:
        project_key = utils.workspace_key()
        result = ctlr.prune_images(project_key)

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
