#!/bin/bash
echo Clear Swarm Setting...
docker swarm leave --force >> /dev/null 2>&1
docker container prune -f >> /dev/null 2>&1
docker network prune -f >> /dev/null 2>&1
docker network create --subnet 10.10.0.0/24 --gateway 10.10.0.1 -o com.docker.network.bridge.enable_icc=false -o com.docker.network.bridge.name=docker_gwbridge docker_gwbridge
docker swarm init $@
