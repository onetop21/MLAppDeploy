import sys
import os
import io
import fnmatch
import tarfile

from typing import Optional

from mlad.cli import config as config_core
from mlad.cli.libs import utils
from mlad.cli.format import (
    DOCKERFILE, DOCKERFILE_ENV, DOCKERFILE_REQ_PIP, DOCKERFILE_REQ_APT,
    DOCKERFILE_REQ_ADD, DOCKERFILE_REQ_RUN, DOCKERFILE_REQ_APK, DOCKERFILE_REQ_YUM
)

from mlad.core.docker import controller as ctlr


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
    for spec in [ctlr.inspect_image(image) for image in images]:
        if len(spec['tags']) == 0:
            untagged += 1
        else:
            row = [
                spec['short_id'],
                spec['username'],
                spec['project_name'],
                spec['tag'],
                spec['maintainer'],
                spec['created']
            ]
            if all:
                row.append(spec['workspace'])
            data.append(row)
    utils.print_table(data[:tail + 1], 'There is no built image.', 0)
    if untagged:
        print(f'This project has {untagged} untagged images. '
              'Delete untagged images to free the disk space. '
              'Use command `mlad image prune`')


def build(file: Optional[str], quiet: bool, no_cache: bool, pull: bool, push: bool = True):
    utils.process_file(file)
    config = config_core.get()
    project = utils.get_project()

    # Generate Base Labels
    workspace = utils.get_workspace()
    registry_address = config_core.get_registry_address(config)
    base_labels = utils.base_labels(
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
        if 'filePath' in workspace:
            with open(workspace['filePath'], 'r') as dockerfile:
                payload = dockerfile.read()
            if os.path.isfile(workspace['ignorePath']):
                with open(workspace['ignorePath'], 'r') as ignorefile:
                    workspace['ignores'] = [
                        line.replace('\n', '') for line in ignorefile.readlines()]
            else:
                workspace['ignores'] = []
        else:
            payload = workspace['buildscript']

    tarbytes = io.BytesIO()
    dockerfile_info = tarfile.TarInfo('.dockerfile')
    dockerfile_info.size = len(payload)
    with tarfile.open(fileobj=tarbytes, mode='w:gz') as tar:
        for name, arcname in _get_arcfiles(project['workdir'], workspace['ignores']):
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
    if project['kind'] != 'Component' and push:
        yield f'Upload the image to the registry [{registry_address}]...'
        for line in ctlr.push_image(repository):
            yield line

    return image


def _obtain_workspace_payload(workspace, maintainer):
    default = {
        'env': workspace.get('env', {}),
        'preps': workspace.get('preps', []),
        'command': workspace.get('command', ''),
        'args': workspace.get('args', ''),
        'script': f'RUN {workspace["script"]}' if 'script' in workspace else ''
    }

    envs = [DOCKERFILE_ENV.format(KEY=k, VALUE=v) for k, v in default['env'].items()]

    preps = default['preps']
    prep_docker_formats = []
    for prep in preps:
        key = tuple(prep.keys())[0]
        template = PREP_KEY_TO_TEMPLATE[key]
        prep_docker_formats.append(template.format(SRC=prep[key]))

    commands = [f'"{item}"' for item in default['command'].split()] + \
               [f'"{item}"' for item in default['args'].split()]

    return DOCKERFILE.format(
        BASE=workspace['base'],
        MAINTAINER=maintainer,
        ENVS='\n'.join(envs),
        PREPS='\n'.join(prep_docker_formats),
        SCRIPT=default['script'],
        COMMAND=f'CMD [{", ".join(commands)}]' if len(commands) > 0 else ''
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


def _get_arcfiles(workspace='.', ignores=[]):
    ignores = [os.path.join(os.path.abspath(workspace), _)for _ in ignores]
    for root, dirs, files in os.walk(workspace):
        for name in files:
            filepath = os.path.join(root, name)
            if not _match_ignores(filepath, ignores):
                yield filepath, os.path.relpath(os.path.abspath(filepath),
                                                os.path.abspath(workspace))
        prune_dirs = []
        for name in dirs:
            dirpath = os.path.join(root, name)
            if _match_ignores(dirpath, ignores):
                prune_dirs.append(name)
        for _ in prune_dirs:
            dirs.remove(_)


def _match_ignores(filepath, ignores):
    result = False
    normpath = os.path.normpath(filepath)

    def matcher(path, pattern):
        patterns = [pattern] + ([os.path.normpath(f"{pattern.replace('**/','/')}")]
                                if '**/' in pattern else [])
        result = map(lambda _: fnmatch.fnmatch(normpath, _) or fnmatch.fnmatch(
            normpath, os.path.normpath(f"{_}/*")), patterns)
        return sum(result) > 0
    for ignore in ignores:
        if ignore.startswith('#'):
            pass
        elif ignore.startswith('!'):
            result &= not matcher(normpath, ignore[1:])
        else:
            result |= matcher(normpath, ignore)
    return result
