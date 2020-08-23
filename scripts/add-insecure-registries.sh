#!/bin/bash

DAEMON_JSON="/etc/docker/daemon.json"
MAX_STEP=4
STEP=0

function Usage {
    echo "Registration Insecure Registry to Docker Swarm(MLAppDeploy)."
    echo "$ $0 [-H,--host docker-host-address] [registry-addresses...]"
    echo "    -H, --host : Address of Docker-Swarm master node."
    echo "    -h, --help : This page"
    exit 1
}

OPTIONS=$(getopt -o hH: --long help,host:,node: -- "$@")
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
        NODE=$1
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
        echo "Timeout to Connect [$HOST]"
    fi
}

if [[ ! -z "$HOST" ]]; then
    HOST_ARGS="-H $HOST"
fi

## Main Script
function GetPrivileged {
    echo "Request sudo privileged."
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
        echo Need to install $1.
        sudo apt install -y $1
    else
        echo Okay
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
        echo "Already registered registry [$1]"
    else
        CONFIG=`echo $CONFIG | jq ".\"insecure-registries\"=[\"$1\"]+.\"insecure-registries\""`
        echo $CONFIG | jq . | sudo dd status=none of=$DAEMON_JSON
    fi
}

GetPrivileged
RequiresFromApt jq
if [[ -z "$NODE" ]]; then
    sudo docker $HOST_ARGS node ls >> /dev/null 2>&1
    if [[ "$?" == "0" ]]; then
        NODE_LIST=`sudo docker $HOST_ARGS node ls -q | xargs docker $HOST_ARGS node inspect | jq '.[].Status.Addr' -r`
        for NODE in $NODE_LIST
        do
            echo "[$NODE] Registering Insecure Registries..."
            read -p "Type administrator username: " USER
            if [[ ! -z "$USER" ]]; then
               USER=$USER@ 
            fi
            RemoteRun $USER$NODE $SCRIPT "--node $NODE -- $@"
        done
    else
        echo Cannot gather node list from Docker-Swarm.
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
