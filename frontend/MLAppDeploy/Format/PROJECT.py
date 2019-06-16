import sys

FORMAT='''# MLAppDeploy Project v0.1
project:
    name: {NAME}
    version: {VERSION}
    author: {AUTHOR}
workspace:
    ## Describe package manager and dependency list to install pre-required.
    #depends:
    #    pip: requirements.txt
    ## Describe environment variables.
    #env:  
    #    PYTHONUNBUFFERED: 1    
    ## Describe exclude files from project.
    #ignore:
    #   - .*
    #   - **/.*
    ## Describe application to execute (Protected)
    #entrypoint: python run.py
    ## Describe arguments for execute application (Overwritable)
    #arguments: --help
services:
    #[SERVICENAME]:
    ## Describe image to run docker service for run not built image from workspace.
    #    image: 
    ## Describe environment variables additionaly.
    #    env:
    #        [KEY]: [VALUE]
    ## Describe services before running current service.
    #    depends: [ SERVICENAME, ... ]
    ## Describe arguments to need overwrite.
    #    arguments:
    #
    ## Deploy only options
    #    deploy:
    ## Describe required system resource quote.
    #        quotes:
    #            cpus: 1
    #            mems: 8G
    #            gpus: 0
    ## Describe target node to run services.
    #        constraints:
    ## Describe number to run service instances.
    #        replicas: 1
    #...
'''

sys.modules[__name__] = FORMAT

