import sys
import json

from typing import Optional, List, Tuple

from dictdiffer import diff

from mlad.cli import config as config_core
from mlad.cli import train
from mlad.cli.libs import utils, interrupt_handler
from mlad.cli.validator import validators
from mlad.cli.exceptions import (
    ImageNotFoundError, InvalidProjectKindError, InvalidUpdateOptionError
)

from mlad.core.docker import controller as docker_ctlr
from mlad.core.default import project as default_project
from mlad.core.libs import utils as core_utils

from mlad.api import API


def serve(file: Optional[str]):

    utils.process_file(file)
    config = config_core.get()
    project = utils.get_project(default_project)
    project = validators.validate(project)

    kind = project['kind']
    if not kind == 'Deployment':
        raise InvalidProjectKindError('Deployment', 'deploy')

    base_labels = core_utils.base_labels(
        utils.get_workspace(),
        config.session,
        project,
        utils.get_registry_address(config)
    )

    project_key = base_labels['MLAD.PROJECT']

    # Find suitable image
    base_key = utils.workspace_key()
    image_tag = base_labels['MLAD.PROJECT.IMAGE']
    images = [image for image in docker_ctlr.get_images(project_key=base_key)
              if image_tag in image.tags]
    if len(images) == 0:
        raise ImageNotFoundError(image_tag)

    # Create a project
    yield 'Deploy apps to the cluster...'
    credential = docker_ctlr.obtain_credential()
    extra_envs = config_core.get_env()
    lines = API.project.create(base_labels, project, extra_envs, credential=credential, allow_reuse=False)
    for line in lines:
        if 'stream' in line:
            sys.stdout.write(line['stream'])
        if 'result' in line and line['result'] == 'succeed':
            break

    # Apply ingress for app
    apps = project.get('app', dict())
    ingress = project['ingress']
    for name, value in ingress.items():
        app_name, port = value['target'].split(':')
        if app_name in apps.keys():
            apps[app_name]['ingress'] = {
                'name': name,
                'rewritePath': value['rewritePath'],
                'port': port
            }

    # Create apps
    app_specs = []
    for name, app_spec in apps.items():
        value['name'] = name
        app_spec = utils.convert_tag_only_image_prop(app_spec, image_tag)
        app_specs.append(app_spec)

    yield 'Start apps...'
    try:
        with interrupt_handler(message='Wait...', blocked=True) as h:
            res = API.app.create(project_key, app_specs)
            if h.interrupted:
                pass
    except Exception as e:
        next(API.project.delete(project_key))
        raise e

    yield 'Done.'
    yield utils.print_info(f'Project key : {project_key}')

    # Get ingress path for deployed app
    address = config['apiserver']['address'].rsplit('/beta')[0]
    for app in res:
        if app['ingress']:
            path = f'{address}{app["ingress"]}'
            yield utils.print_info(f'[{app["name"]}] Ingress Path : {path}')


def kill(project_key: str, no_dump: bool):
    return train.down(None, project_key, no_dump)


def kill_force(project_key: str, no_dump: bool):
    return train.down_force(None, project_key, no_dump)


def scale(scales: List[Tuple[str, int]], project_key: str):
    return train.scale(scales, None, project_key)


def ingress():
    config = config_core.get()
    address = config['apiserver']['address'].rsplit('/beta')[0]
    specs = API.app.get()['specs']
    rows = [('USERNAME', 'PROJECT NAME', 'APP NAME', 'KEY', 'PATH')]
    for spec in specs:
        if spec['ingress'] != '':
            username = spec['username']
            project_name = spec['project']
            app_name = spec['name']
            key = spec['key']
            path = f'{address}{spec["ingress"]}'
            rows.append((username, project_name, app_name, key, path))
    utils.print_table(rows, 'Cannot find running deployments', 0, False)


def update(project_key: str, file: Optional[str]):

    project = API.project.inspect(project_key=project_key)
    cur_project_yaml = json.loads(project['project_yaml'])

    utils.process_file(file)
    project = utils.get_project(default_project)
    project = validators.validate(project)

    kind = project['kind']
    if not kind == 'Deployment':
        raise InvalidProjectKindError('Deployment', 'deploy')

    update_key_store = ['image', 'command', 'args', 'scale', 'env', 'quota']

    cur_apps = cur_project_yaml['app']
    update_apps = project['app']

    def _validate(key: str):
        if key not in update_key_store:
            raise InvalidUpdateOptionError(key)

    # Get diff from project yaml
    update_specs = []
    diff_keys = {}
    for name, app in cur_apps.items():
        update_app = update_apps[name]

        env = {
            'current': app['env'] if 'env' in app else {},
            'update': update_app['env'] if 'env' in update_app else {}
        }

        update_spec = {key: (env if key == 'env' else update_app.get(key, None)) 
                       for key in update_key_store}
        update_spec['name'] = name

        diff_keys[name] = set()
        diffs = list(diff(app, update_app))
        for diff_type, key, value in diffs:
            key = key.split('.')[0]

            if diff_type == 'change':
                _validate(key)
                diff_keys[name].add(key)
            else:
                if key != '':
                    _validate(key)
                    diff_keys[name].add(key)
                else:
                    for key, value in value:
                        _validate(key)
                        diff_keys[name].add(key)

        if len(diff_keys[name]) > 0:
            update_specs.append(update_spec)

    for name, keys in diff_keys.items():
        if len(keys) > 0:
            yield f'Update {list(keys)} for app "{name}"...'

    if len(update_specs) > 0:
        API.project.update(project_key, project, update_specs)
        yield 'Done.'
    else:
        yield 'No changes to update.'
