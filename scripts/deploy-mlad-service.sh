#!/bin/bash

function ColorEcho {
    COLOR="\033[0m"
    if [[ "$1" == "ERROR" ]]; then
        COLOR="\033[0;31m"
        shift;
    elif [[ "$1" == "WARN" ]]; then
        COLOR="\033[0;33m"
        shift;
    elif [[ "$1" == "INFO" ]]; then
        COLOR="\033[0;32m"
        shift;
    elif [[ "$1" == "DEBUG" ]]; then
        COLOR="\033[0;34m"
        shift;
    fi

    echo -e "$COLOR$@\033[0m"
}

function Usage {
    ColorEcho INFO "Deploy default services for MLAppDeploy environment."
    ColorEcho "$ $0 [-H,--host docker-host-address] [minio|registry]"
    ColorEcho "    -H, --host : Address of Docker-Swarm master node."
    ColorEcho "    -h, --help : This page"
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

function IsInstalled {
    echo $(which $1 | wc -l)
}

function RequiresFromApt {
    printf "Check requires [$1]... "
    if [[ `IsInstalled $1` == '0' ]]; then
        ColorEcho WARN Need to install $1.
        sudo apt install -y $1
    else
        ColorEcho DEBUG Okay
    fi
}


if [[ "$HOST" != *":"* ]]; then
    if [[ -z "$HOST" ]]; then
        export DOCKER_HOST=
    else
        export DOCKER_HOST=$HOST:2375
    fi
else
    export DOCKER_HOST=$HOST
fi

if [[ -z "$DOCKER_HOST" ]]; then
    ColorEcho WARN "Deploy default services to localhost."
else
    ColorEcho INFO "Deploy default services to $DOCKER_HOST."
fi

read -p "Type Access Key of MinIO (Default: MLAPPDEPLOY) : " ACCESS_KEY
export ACCESS_KEY
read -p "Type Secret Key of MinIO (Default: MLAPPDEPLOY) : " SECRET_KEY
export SECRET_KEY

docker-compose -p MLAppDeploy -f `dirname $0`/services/default-services.yaml up -d $@
