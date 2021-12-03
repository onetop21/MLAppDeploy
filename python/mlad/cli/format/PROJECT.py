import sys


FORMAT = '''# MLAppDeploy Project v0.3
apiVersion: v1                      # [OPTIONAL] Describe api version. (*v1)
maintainer: {MAINTAINER}            # [OPTIONAL] Describe maintainer. (*env.USER)
name: {NAME}                        # Describe project name.
version: {VERSION}                  # [OPTIONAL] Describe verison. (*1.0.0)
workdir: .                          # [OPTIONAL] Describe working directory. (*.)
ingress:                            # [OPTIONAL] Describe ingress to expose.
    #[NAME]:
    #    rewritePath: true
    #    target: SERVICENAME:8080
workspace:
    #kind: Workspace                # Describe kind of workspace. (*Workspace, Dockerfile)
    #base: python:latest            # Describe base docker image tag.
    #command: python test.py        # [OPTIONAL] Describe application to execute.
    #args: temp                     # [OPTIONAL] Describe arguments for execute application.
    #preps:                         # [OPTIONAL] Describe prepare options for run.
    #   - pip: requirements.txt
    #env:                           # [OPTIONAL] Describe environment variables.
    #    PYTHONUNBUFFERED: 1
    #ignore:                        # [OPTIONAL] Describe exclude files from project.
    #   - "**/.*"
    #script: python script.py       # [OPTIONAL] Describe script for run.
    #-------------------------------#
    #kind: Dockerfile               # Describe kind of workspace. (*Workspace, Dockerfile)
    #script: |                      # Describe Dockerfile script.
    #   FROM python:latest
    #   RUN echo "hello world"
    #ignores:                       # [OPTIONAL] Describe exclude files from project.
    #   - "**/.*"
    #filePath: .                    # Describe Dockerfile path. (Instead of defining script.)
    #ignorePath: ./data             # [OPTIONAL] Describe exclude file path. (Instead of defining ignores)
app:
    ### Describe 'App' to run.
    #[NAME]:
    #    kind: App                  # [OPTIONAL] Describe kind of app. (*App, Job, Service)
    #    image: mongo               # [OPTIONAL] Describe image to run app for run not built image from workspace.
    #    command: python test.py    # [OPTIONAL] Describe command to need overwrite.
    #    constraints:               # [OPTIONAL] Describe target node to run app.
    #        hostname: node1
    #        label:
    #            [KEY]: [VALUE]
    #    env:
    #        [KEY]: [VALUE]         # [OPTIONAL] Describe environment variables additionaly.
    #    ports: [80,...]            # [OPTIONAL] Describe expose ports to other apps.
    #    args: temp                 # [OPTIONAL] Describe arguments to need overwrite.
    #    mounts:                    # [OPTIONAL] Describe mounts.
    #       - '/host-path:/mnt-path'
    #    scale: 1                   # [OPTIONAL] Describe number of replicas or parallelism. (*1)
    #    quota:                     # [OPTIONAL] Describe required system resource quota.
    #        cpu: 1
    #        gpu: 0
    #        mem: 8G
    #    restartPolicy: never       # [OPTIONAL] Describe restart policy. (*never, onFailure, always)
    ### Describe 'Job' to run.
    #[NAME]:
    ## Available fields from app - image, env, ports, command, args, mounts, constraints
    #    kind: Job                  # [OPTIONAL] Describe kind of app. (*App, Job, Service)
    #    runSpec:                   # [OPTIONAL] Describe spec for running Job.
    #        restartPolicy: never   # [OPTIONAL] Describe restart policy. (*never, onFailure)
    #        parallelism: 1         # [OPTIONAL] (*1)
    #        completion: 1          # [OPTIONAL] (*1)
    #    resources:                 # [OPTIONAL] Describe resource specifically for the Job.
    #        limits:
    #            cpu: 1
    #            gpu: 0
    #            mem: 8G
    #        requests:
    #            cpu: 1
    #            gpu: 0
    #            mem: 8G
    ### Describe 'Service' to run.
    #[NAME]:
    ## Available fields from app - image, env, ports, command, args, mounts, constraints
    #    kind: Service              # [OPTIONAL] Describe kind of app. (*App, Job, Service)
    #    runSpec:                   # [OPTIONAL] Describe spec for running Service.
    #        replicas: 1
    #    resources:                 # [OPTIONAL] Describe resource for the Job
    #        limits:
    #            cpu: 1
    #            gpu: 0
    #            mem: 8G
    #        requests:
    #            cpu: 1
    #            gpu: 0
    #            mem: 8G
'''

sys.modules[__name__] = FORMAT