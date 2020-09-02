#!/bin/bash
function Usage {
    echo "Registration Insecure Registry to Docker Swarm(MLAppDeploy)."
    echo "$ $0 [-H,--host docker-host-address] [registry-addresses...]"
    echo "    -H, --host : Address of Docker-Swarm master node."
    echo "    -h, --help : This page"
    exit 1
}

OPTIONS=$(getopt -o hH: --long help,host: -- "$@")
[ $? -eq 0 ] || Usage
eval set -- "$OPTIONS"
while true; do
    case "$1" in
    -H|--host) shift
        HOST=$1
        ;;
    -h|--help)
        Usage
        ;;
    --)
        shift
        break
        ;;
    esac
    shift
done

if [[ ! -z "$HOST" ]]; then
    export DOCKER_HOST=$HOST
fi

if [[ "$DOCKER_HOST" != *":"* ]]; then
    export DOCKER_HOST=$DOCKER_HOST:2375
fi


if [[ -z "$DOCKER_HOST" ]]; then
    echo "Deploy default services to localhost."
else
    echo "Deploy default services to $DOCKER_HOST."
fi

read -p "Type Access Key of MinIO (Default: MLAPPDEPLOY) : " ACCESS_KEY
export ACCESS_KEY
read -p "Type Secret Key of MinIO (Default: MLAPPDEPLOY) : " SECRET_KEY
export SECRET_KEY

docker-compose -p MLAppDeploy -f services/default-services.yaml up -d
