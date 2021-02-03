#!/bin/bash
docker build -t mlad/service -f MLADService-Dockerfile .
docker service create --name mlad-service -p 8440:8440 --mount 'type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock' mlad/service
