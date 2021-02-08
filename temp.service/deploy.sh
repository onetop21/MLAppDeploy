#!/bin/bash

if [[ "$1" == "build" ]]; then
    #docker build -t mlad/service -f MLADService-Dockerfile .
    docker build -t mlad/service -f MLADService-Dockerfile ..
elif [[ "$1" == "up" ]]; then
    docker service create --name mlad-service -p 8440:8440 --mount 'type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock' mlad/service
elif [[ "$1" == "down" ]]; then
    docker service rm mlad-service
else
    echo "MLAppDeploy Deployment Script"
    echo "$ bash $0 [build,up,down]"
fi
