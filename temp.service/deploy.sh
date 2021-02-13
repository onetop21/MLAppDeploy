#!/bin/bash

if [[ "$1" == "build" ]]; then
    #docker build -t mlad/service -f MLADService-Dockerfile .
    docker build -t mlad/service -f MLADService-Dockerfile ..
elif [[ "$1" == "dev" ]]; then
    docker service create -q --name mlad-service -e MLAD_DEBUG=1 -e PYTHONUNBUFFERED=1 -p 8440:8440 --mount 'type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock' mlad/service \
    && docker service logs mlad-service 2>&1 | head -n1 | awk '{print "Admin Token: " $6}'
elif [[ "$1" == "up" ]]; then
    docker service create -q --name mlad-service -e PYTHONUNBUFFERED=1 -p 8440:8440 --mount 'type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock' mlad/service \
    && docker service logs mlad-service 2>&1 | head -n1 | awk '{print "Admin Token: " $6}'
elif [[ "$1" == "down" ]]; then
    docker service rm mlad-service
else
    echo "MLAppDeploy Deployment Script"
    echo "$ bash $0 [build,dev,up,down]"
fi
