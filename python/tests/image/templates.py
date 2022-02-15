import os


def setup():
    with open('mlad-test-requirements.txt', 'w') as f:
        f.write('pyzmq')

    with open('mlad-test-add.txt', 'w') as f:
        f.write('hello world')

    with open('mlad-test-dockerfile', 'w') as f:
        f.write(TEST_DOCKERFILE)


def teardown():
    os.remove('mlad-test-requirements.txt')
    os.remove('mlad-test-add.txt')
    os.remove('mlad-test-dockerfile')


def _indent_func(x: str):
    return ' ' * 8 + x


TEST_DOCKERFILE = '''
FROM python:3.7-slim
MAINTAINER mlad

ENV PYTHONUNBUFFERED 1
ENV HELLO WORLD

WORKDIR /workspace

COPY mlad-test-requirements.txt .depends/pip.list
RUN pip install -r .depends/pip.list
ADD mlad-test-add.txt mlad-test-add.txt
RUN cat mlad-test-add.txt

COPY . .

RUN echo .

CMD []
'''

INDENTED_DOCKERFILE = '\n'.join(list(map(_indent_func, TEST_DOCKERFILE.split('\n'))))

TEMPLATE1 = '''
apiVersion: v1
maintainer: mlad
name: template1
version: 0.0.1
workdir: .
workspace:
    kind: Workspace
    base: python:3.7-slim
    preps:
    - pip: mlad-test-requirements.txt
    - add: mlad-test-add.txt
    - run: cat mlad-test-add.txt
    env:
        HELLO: WORLD
app:
    test:
        command: python templates.py

'''

TEMPLATE2 = f'''
apiVersion: v1
maintainer: mlad
name: template2
version: 0.1.0
workdir: .
workspace:
    kind: Buildscript
    buildscript: | {INDENTED_DOCKERFILE}
app:
    test:
        command: python templates.py

'''

TEMPLATE3 = '''
apiVersion: v2
maintainer: mlad
name: template3
version: 1.0.0
workdir: .
workspace:
    kind: Dockerfile
    filePath: mlad-test-dockerfile
app:
    test:
        command: python templates.py
'''
