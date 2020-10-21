#!/bin/bash

DAEMON_JSON="/etc/docker/daemon.json"
MAX_STEP=4
STEP=0

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
    ColorEcho INFO "Registration Insecure Registry to Docker Swarm(MLAppDeploy)."
    ColorEcho "$ $0 [-H,--host docker-host-address] [registry-addresses...]"
    ColorEcho "    -H, --host : Address of Docker-Swarm master node."
    ColorEcho "    -h, --help : This page"
    exit 1
}

OPTIONS=$(getopt -o hH: --long help,host:,node -- "$@")
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
    --node)
        IS_NODE=1
        ;;
    --)
        shift
        break
        ;;
    esac
    shift
done

function RemoteRun {
    FILENAME=`basename $0`
    HOST=$1; shift
    if [[ "$HOST" == *"@"* ]]; then
        ADDR=($(echo $HOST | tr "@" "\n"))
        OPEN=`nc -v -z ${ADDR[1]} 22 -w 3 >> /dev/null 2>&1; echo $?`
    else
        OPEN=`nc -v -z $HOST 22 -w 3 >> /dev/null 2>&1; echo $?`
    fi
    if [[ "$OPEN" == "0" ]]; then
        SCRIPT="echo '$(base64 -w0 $0)' > /tmp/$FILENAME.b64; base64 -d /tmp/$FILENAME.b64 > /tmp/$FILENAME; bash /tmp/$FILENAME"
        ssh -t $HOST $SCRIPT $@
    else
        ColorEcho ERROR "Timeout to Connect [$HOST]"
    fi
}

if [[ ! -z "$HOST" ]]; then
    HOST_ARGS="-H $HOST"
else
    HOST_ARGS=""
fi

## Main Script
function GetPrivileged {
    ColorEcho WARN "Request sudo privileged."
    sudo ls >> /dev/null 2>&1
    if [[ ! "$?" == "0" ]]; then
        exit 1
    fi
}

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

function TouchDaemonJSON {
    # If no file
    if [[ ! -f "$DAEMON_JSON" ]]; then
        echo '{}' | sudo dd status=none of=$DAEMON_JSON
    elif [[ -z `sudo cat $DAEMON_JSON` ]]; then
        # If empty file
        echo '{}' | sudo dd status=none of=$DAEMON_JSON
    fi
}

function AppendInsecureRegistries {
    CONFIG=`sudo cat $DAEMON_JSON`
    if [ "`echo $CONFIG | jq '."insecure-registries"'`" == "null" ]; then
        CONFIG=`echo $CONFIG | jq '."insecure-registries"=[]'`
    fi
    if [ `echo $CONFIG | jq '."insecure-registries"' | grep $1 >> /dev/null; echo $?` == "0" ]; then
        ColorEcho INFO "Already registered registry [$1]"
    else
        CONFIG=`echo $CONFIG | jq ".\"insecure-registries\"=[\"$1\"]+.\"insecure-registries\""`
        echo $CONFIG | jq . | sudo dd status=none of=$DAEMON_JSON
    fi
}

GetPrivileged
RequiresFromApt jq
if [[ -z "$IS_NODE" ]]; then
    sudo docker $HOST_ARGS node ls >> /dev/null 2>&1
    if [[ "$?" == "0" ]]; then
        NODE_LIST=`sudo docker $HOST_ARGS node ls -q | xargs docker $HOST_ARGS node inspect | jq '.[].Status.Addr' -r`
        for NODE in $NODE_LIST
        do
            ColorEcho INFO "[$NODE] Registering Insecure Registries..."
            read -p "Type administrator username: " USER
            if [[ ! -z "$USER" ]]; then
               USER=$USER@ 
            fi
            RemoteRun $USER$NODE "--node -- $@"
        done
    else
        ColorEcho WARN Cannot gather node list from Docker-Swarm.
        exit $?
    fi
else
    TouchDaemonJSON
    for TARGET in $@
    do
        AppendInsecureRegistries $TARGET
    done

    sudo systemctl daemon-reload
    sudo systemctl restart docker.service
fi
