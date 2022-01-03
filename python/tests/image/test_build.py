import os

from mlad.cli.image import (
    build, remove, _obtain_workspace_payload
)
from mlad.cli.libs import utils
from . import templates


def setup_module():
    templates.setup()


def teardown_module():
    templates.teardown()
    os.remove('mlad-test-template1.yml')
    os.remove('mlad-test-template2.yml')
    os.remove('mlad-test-template3.yml')


def test_manifest_template1():
    with open('mlad-test-template1.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)
    os.environ['MLAD_PRJFILE'] = 'mlad-test-template1.yml'
    manifest = utils.get_manifest()
    assert manifest == {
        'apiVersion': 'v1',
        'name': 'template1',
        'version': '0.0.1',
        'maintainer': 'mlad',
        'workdir': os.getcwd(),
        'workspace': {
            'kind': 'Workspace',
            'base': 'python:3.7-slim',
            'preps': [
                {'pip': 'mlad-test-requirements.txt'},
                {'add': 'mlad-test-add.txt'},
                {'run': 'cat mlad-test-add.txt'}
            ],
            'script': '',
            'env': {
                'PYTHONUNBUFFERED': 1,
                'HELLO': 'WORLD'
            },
            'ignores': ['**/.*'],
            'command': '',
            'arguments': '',
        },
        'ingress': {},
        'app': {
            'test': {'command': 'python templates.py'}
        }
    }


def test_workspace_payload():
    with open('mlad-test-template1.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)
    os.environ['MLAD_PRJFILE'] = 'mlad-test-template1.yml'
    manifest = utils.get_manifest()
    workspace = manifest['workspace']
    payload = _obtain_workspace_payload(workspace, manifest['maintainer'])
    assert payload == templates.TEST_DOCKERFILE


def test_template1():
    with open('mlad-test-template1.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)

    os.environ['MLAD_PRJFILE'] = 'mlad-test-template1.yml'
    image = build(False, True, False)
    labels = image.labels
    assert labels['MLAD.PROJECT.API_VERSION'] == 'v1'
    assert labels['MLAD.PROJECT.MAINTAINER'] == 'mlad'
    assert labels['MLAD.PROJECT.NAME'] == 'template1'
    assert labels['MLAD.PROJECT.VERSION'] == '0.0.1'
    assert labels['MLAD.PROJECT.WORKSPACE'].endswith(f'{os.getcwd()}/mlad-test-template1.yml')
    remove([image.id], True)


def test_manifest_template2():
    with open('mlad-test-template2.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE2)
    os.environ['MLAD_PRJFILE'] = 'mlad-test-template2.yml'
    manifest = utils.get_manifest()
    assert manifest == {
        'apiVersion': 'v1',
        'name': 'template2',
        'version': '0.1.0',
        'maintainer': 'mlad',
        'workdir': os.getcwd(),
        'workspace': {
            'kind': 'Dockerfile',
            'script': templates.TEST_DOCKERFILE[1:],
            'ignores': ['**/.*']
        },
        'ingress': {},
        'app': {
            'test': {'command': 'python templates.py'}
        }
    }


def test_template2():
    with open('mlad-test-template2.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)

    os.environ['MLAD_PRJFILE'] = 'mlad-test-template2.yml'
    image = build(False, True, False)
    remove([image.id], True)


def test_template3():
    with open('mlad-test-template3.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE3)

    os.environ['MLAD_PRJFILE'] = 'mlad-test-template3.yml'
    image = build(False, True, False)
    remove([image.id], True)
