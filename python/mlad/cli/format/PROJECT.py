import sys


FORMAT = '''# MLAppDeploy Project v0.3.2
apiVersion: v1
maintainer: {MAINTAINER}
name: {NAME}
version: {VERSION}
workspace:
  kind: Workspace
  base: python:latest
  env:
    PYTHONUNBUFFERED: 1
  preps:
  - pip: requirements.txt
  command: python main.py
app:
  app-name:
    kind: Job
'''

sys.modules[__name__] = FORMAT
