import sys

FORMAT='''# MLAppDeploy Project v0.2
project:
    name: {NAME}
    version: {VERSION}
    maintainer: {MAINTAINER}
    #workdir: .                     # Describe workspace directory.
workspace:
    #base: python:latest            # Describe base docker image tag
    #requires:                      # Describe package manager and dependency list to install pre-required.
    #    pip: requirements.txt
    #env:                           # Describe environment variables.
    #    PYTHONUNBUFFERED: 1        
    #ignore:                        # Describe exclude files from project.
    #   - "**/.*"
    #prescripts: []                 # Describe Pre-scripts for preparing.
    #postscripts: []                # Describe Post-scripts for preparing.
    #command: python run.py         # Describe application to execute
    #arguments: --help              # Describe arguments for execute application
services:
    #[SERVICENAME]:
    #    image:                     # Describe image to run docker service for run not built image from workspace.
    #    env:                       # Describe environment variables additionaly.
    #        [KEY]: [VALUE]
    #    command:                   # Describe command to need overwrite.
    #    arguments:                 # Describe arguments to need overwrite.
    #    ports: [80,...]            # Describe expose ports to other services.
    #    deploy:                    # Deploy only options
    #        restart_policy: always # Describe restart policy. (never, on-failure, always)
    #        quota:                 # Describe required system resource quota.
    #            cpus: 1
    #            mems: 8G
    #            gpus: 0
    #        constraints:           # Describe target node to run services.
    #            hostname:
    #            label:
    #        replicas: 1            # Describe number to run service instances.
    #...
'''

sys.modules[__name__] = FORMAT

