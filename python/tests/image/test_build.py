import os
import sys
import io

from mlad.cli.image import (
    build, remove, _obtain_workspace_payload
)
from mlad.cli import config
from mlad.cli.libs import utils
from mlad.core.default import project as default_project
from . import templates


class Generator:
    def __init__(self, gen):
        self.gen = gen

    def __iter__(self):
        self.value = yield from self.gen


def setup_module():
    templates.setup()
    inputs = [
        'https://abc.defg.com',
        'https://abc.defg.com',
        'gameai',
        'https://localhost:9000',
        'us-west-1',
        'minioadmin',
        'minioadmin',
        'mongodb://localhost:27017',
        'dbadmin',
        'dbadmin'
    ]
    sys.stdin = io.StringIO(''.join([f'{_}\n' for _ in inputs[1:]]))
    config.add('test-build', inputs[0], False)


def teardown_module():
    templates.teardown()
    os.remove('mlad-test-template1.yml')
    os.remove('mlad-test-template2.yml')
    os.remove('mlad-test-template3.yml')
    config.delete('test-build')


def test_project_template1():
    with open('mlad-test-template1.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)
    os.environ['MLAD_PRJFILE'] = 'mlad-test-template1.yml'
    project = utils.get_project(default_project)
    assert project == {
        'apiVersion': 'v1',
        'name': 'template1',
        'version': '0.0.1',
        'kind': 'Train',
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
            'args': '',
        },
        'app': {
            'test': {'command': 'python templates.py'}
        }
    }


def test_workspace_payload():
    with open('mlad-test-template1.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)
    os.environ['MLAD_PRJFILE'] = 'mlad-test-template1.yml'
    project = utils.get_project(default_project)
    workspace = project['workspace']
    payload = _obtain_workspace_payload(workspace, project['maintainer'])
    assert payload == templates.TEST_DOCKERFILE


def test_template1():
    with open('mlad-test-template1.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)
    gen = Generator(build('mlad-test-template1.yml', True, False, False, push=False))
    for x in gen:
        pass
    image = gen.value
    labels = image.labels
    assert labels['MLAD.PROJECT.API_VERSION'] == 'v1'
    assert labels['MLAD.PROJECT.MAINTAINER'] == 'mlad'
    assert labels['MLAD.PROJECT.NAME'] == 'template1'
    assert labels['MLAD.PROJECT.VERSION'] == '0.0.1'
    assert labels['MLAD.PROJECT.WORKSPACE'].endswith(f'{os.getcwd()}/mlad-test-template1.yml')
    remove([image.id], True)


def test_project_template2():
    with open('mlad-test-template2.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE2)
    os.environ['MLAD_PRJFILE'] = 'mlad-test-template2.yml'
    project = utils.get_project(default_project)
    assert project == {
        'apiVersion': 'v1',
        'name': 'template2',
        'version': '0.1.0',
        'maintainer': 'mlad',
        'kind': 'Train',
        'workdir': os.getcwd(),
        'workspace': {
            'kind': 'Buildscript',
            'buildscript': templates.TEST_DOCKERFILE[1:],
            'ignores': ['**/.*']
        },
        'app': {
            'test': {'command': 'python templates.py'}
        }
    }


def test_template2():
    with open('mlad-test-template2.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE1)
    gen = Generator(build('mlad-test-template2.yml', True, False, False, push=False))
    for x in gen:
        pass
    image = gen.value
    remove([image.id], True)


def test_template3():
    with open('mlad-test-template3.yml', 'w') as yml_file:
        yml_file.write(templates.TEMPLATE3)
    gen = Generator(build('mlad-test-template3.yml', True, False, False, push=False))
    for x in gen:
        pass
    image = gen.value
    remove([image.id], True)
