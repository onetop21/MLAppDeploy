#!/bin/bash

options=$(getopt -o r:b: --long remote: --long bind: -- "$@")
[ $? -eq 0 ] || {
    echo "Incorrect option privided."
    echo "$ $0 [-b,--bind master-address] [-r,--remote ssh-address]"
    echo "    -b, --bind   : Bind to master after install MLAppDeploy node. (Only node mode.)"
    echo "                   If not define *bind* option to install master mode."
    echo "    -r, --remote : Install MLAppDeploy Environment to Remote machine."
    exit 1
}
eval set -- "$OPTIONS"
while true; do
    echo $1
    case "$1" in
    -r) shift
        REMOTE=$1
        echo Remote: $REMOTE
        ;;
    --remote)
        shift
        REMOTE=$1
        echo Remote: $REMOTE
        ;;
    -b) shift
        BIND=$1
        echo Bind: $BIND
        ;;
    --bind)
        shift
        BIND=$1
        echo Bind: $BIND
        ;;
    --)
        shift
        break
        ;;
    esac
    shift
done

exit 1

DAEMON_JSON="/etc/docker/daemon.json"
MAX_STEP=7
STEP=0

function PrintStep {
    STEP=$((STEP+1))
    echo "[$STEP/$MAX_STEP] $@"
}

function GetPriveleged {
    echo "Request sudo privileged."
    sudo ls >> /dev/null 2>&1
    if [[ ! "$?" == "0" ]]; then
        exit 1
    fi
}

function IsInstalled {
    echo $(which $1 | wc -l)
}

function IsWSL2 {
    echo $(uname -r | grep microsoft-standard | wc -l)
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

function UninstallOnSnapWithWarning {
    if [[ `IsInstalled snap` != '0' ]]; then
        if [[ `snap list $1 >> /dev/null 2>&1 ; echo $?` == '0' ]]; then
            echo "Need to remove $1 from Snapcraft."
            read -n1 -r -p  "If you want to stop installation, Press CTRL+C to break, otherwise any key to continue."
            sudo snap remove --purge $1

            # Clean : https://docs.docker.com/engine/install/ubuntu/#uninstall-docker-engine
            sudo apt-get purge docker-ce docker-ce-cli containerd.io
            sudo rm -rf /var/lib/docker
        fi
    fi
}

function InstallDocker {
    # below script from https://docs.docker.com/engine/install/ubuntu/
    # Uninstall old version
    sudo apt-get remove -y docker docker-engine docker.io containerd runc

    # Update package manager
    sudo apt-get update

    # Install package to use repository over HTTPS
    sudo apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg-agent \
        software-properties-common

    # Add official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

    # Verify fingerprint
    sudo apt-key fingerprint 0EBFCD88

    # Add docker repository
    sudo add-apt-repository \
       "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
       $(lsb_release -cs) \
       stable"

    # Update added docker repository
    sudo apt-get update

    # Install docker community version (latest)
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io
}

function VerifyDocker {
    echo `sudo docker run -it --rm $@ hello-world > /dev/null 2>&1; echo $?`
}

function InstallNVIDIAContainerRuntime2008 {
    # https://github.com/NVIDIA/nvidia-container-runtime
    sudo apt-get install -y nvidia-container-runtime

}

function InstallNVIDIAContainerRuntime2001 {
    # Deprecated Method Officialy

    # If you have nvidia-docker 1.0 installed: we need to remove it and all existing GPU containers
    docker volume ls -q -f driver=nvidia-docker | xargs -r -I{} -n1 docker ps -q -a -f volume={} | xargs -r docker rm -f
    sudo apt-get purge -y nvidia-docker

    # Add the package repositories
    curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | \
      sudo apt-key add -
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
      sudo tee /etc/apt/sources.list.d/nvidia-docker.list
    sudo apt-get update

    # Install nvidia-docker2 and reload the Docker daemon configuration
    sudo apt-get install -y nvidia-docker2 jq
    sudo pkill -SIGHUP dockerd
}

function InstallNVIDIAContainerRuntime {
    echo `InstallNVIDIAContainerRuntime2008; echo $?`
}

function VerifyNVIDIAContainerRuntime {
    echo `sudo docker run -it --rm --gpus hello-world > /dev/null 2>&1; echo $?`
}

function NVIDIAContainerRuntimeConfiguration {
    if [[ ! -f "$DAEMON_JSON" ]]; then
        echo '{}' | sudo dd status=none of=$DAEMON_JSON
    fi

    # Read Daemon.json
    CONFIG=`sudo cat $DAEMON_JSON`
    # Check nvidia runtime in daemon.json
    if [ "`echo $CONFIG | jq '.runtimes.nvidia'`" == "null" ];
    then
        CONFIG=`echo $CONFIG | jq '.runtimes.nvidia={"path":"nvidia-container-runtime", "runtimeArgs":[]}'`
    fi
    echo $CONFIG | jq . | sudo dd status=none of=$DAEMON_JSON
}

function UpdateGPUResources {
    if [[ ! -f "$DAEMON_JSON" ]]; then
        echo '{}' | sudo dd status=none of=$DAEMON_JSON
    fi

    # Enable GPU on docker swarm
    GPU_IDS=`nvidia-smi -a | grep UUID | awk '{print substr($4,0,12)}'`
    CONFIG=`sudo cat $DAEMON_JSON | jq '."default-runtime"="nvidia"' | jq '."node-generic-resources"=[]'`
    for ID in $GPU_IDS; do
        CONFIG=`echo $CONFIG | jq '."node-generic-resources"=["gpu='$ID'"]+."node-generic-resources"'`
    done
    echo $CONFIG | jq . | sudo dd status=none of=$DAEMON_JSON
}

function AdvertiseGPUonSwarm {
    # Advertise GPU device to swarm.
    sudo sed -i -e 's/#swarm-resource/swarm-resource/' /etc/nvidia-container-runtime/config.toml
}  

# Start Script
GetPriveleged

# Step 1: Install Requires
PrintStep Install Requires Utilities.
RequiresFromApt jq

# Step 2: Install Docker
PrintStep Install Docker.
if [[ `IsWSL2` == '1' && `IsINstalled docker` == '1' ]]; then
    echo "Need to install Docker Desktop yourself on WSL2."
    echo "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/wsl/"
    exit
else
    UninstallOnSnapWithWarning docker
    if [[ `IsInstalled docker` == '0' ]]; then
        InstallDocker

        # Add user to docker group
        sudo adduser $USER docker
    fi

    if [[ `VerifyDocker` != "0" ]];
    then
        echo "Need to reboot and retry install to continue install docker for MLAppDeploy."
        exit 0
    fi
fi

PrintStep Install NVIDIA Container Runtime.
# Check Nvidia Driver status
if [ `IsInstalled nvidia-smi` == "0" ];
then
    echo "Cannot find NVIDIA Graphic Card."
else
    if [ `VerifyDocker --gpus all` == "0" ];
    then
        echo "Already installed NVIDIA container runtime."
    else
        echo "Install NVIDIA container runtime."

        InstallNVIDIAContainerRuntime
        NVIDIAContainerRuntimeConfiguration
        UpdateGPUResources
        AdvertiseGPUonSwarm
    fi
fi

# --remote 192.168.0.102
# --node=master 
# --node=worker --master=172.20.41.139
# A POSIX variable
OPTIND=1         # Reset in case getopts has been used previously in the shell.

# Initialize our own variables:
output_file=""
verbose=0

while getopts "h?vf:" opt; do
    case "$opt" in
    h|\?)
        show_help
        exit 0
        ;;
    v)  verbose=1
        ;;
    f)  output_file=$OPTARG
        ;;
    esac
done

shift $((OPTIND-1))

[ "${1:-}" = "--" ] && shift

echo "verbose=$verbose, output_file='$output_file', Leftovers: $@"

exit

# Intro
if [[ "$IS_WSL2" == "0" ]];
then
    echo "============================="
    echo " Installation of MLAppDeploy"
    echo " "
    echo " 1. MASTER NODE"
    echo " 2. WORKER NODE (Default)"
    echo "============================="
    SHOULD_RUN=1
    while [ "$SHOULD_RUN" == "1" ];
    do
        read -p "What is node this machine? " NODE_TYPE
        if [ -z $NODE_TYPE ];
        then
            NODE_TYPE=2
        fi

        if [ "$NODE_TYPE" -lt "1" ] || [ "$NODE_TYPE" -gt "2" ];
        then
            echo "Invalid node type."
            continue
        fi
        SHOULD_RUN=0
    done

    if [ "$NODE_TYPE" == "1" ];
    then
        # Enable Remote on Master Node
        if [[ -z `sudo cat $DAEMON_JSON` ]]; then
            echo '{}' | sudo dd status=none of=$DAEMON_JSON
        fi
        
        CONFIG=`sudo cat $DAEMON_JSON`
        IS_EXIST_SOCK=`echo $CONFIG | jq '.hosts' | grep "unix:///var/run/docker.sock" | wc -l`
        IS_EXIST_TCP=`echo $CONFIG | jq '.hosts' | grep "tcp://0.0.0.0" | wc -l`
        if [ "$IS_EXIST_SOCK" == "0" ];
        then
            CONFIG=`echo $CONFIG | jq '."hosts"=["unix:///var/run/docker.sock"]+."hosts"'`
        fi
        if [ "$IS_EXIST_TCP" == "0" ];
        then
            CONFIG=`echo $CONFIG | jq '."hosts"=["tcp://0.0.0.0"]+."hosts"'`
        fi
        echo $CONFIG | jq . | sudo dd status=none of=$DAEMON_JSON

        sudo sed -i 's/dockerd\ \-H\ fd\:\/\//dockerd/g' /lib/systemd/system/docker.service

        sudo systemctl daemon-reload
        sudo systemctl restart docker.service

        echo Clear Swarm Setting...
        docker swarm leave --force >> /dev/null 2>&1
        docker container prune -f >> /dev/null 2>&1
        docker network prune -f >> /dev/null 2>&1
        docker network create --subnet 10.10.0.0/24 --gateway 10.10.0.1 -o com.docker.network.bridge.enable_icc=false -o com.docker.network.bridge.name=docker_gwbridge docker_gwbridge
        JOIN_RESULT=`docker swarm init $@ 1>/dev/null`
        if [ "$?" != "0" ];
        then
            echo $JOIN_RESULT
        else
            echo "Docker Swarm Initialized. (3/3)"
        fi
    elif [ "$NODE_TYPE" == "2" ];
    then
        echo Clear Swarm Setting...
        docker swarm leave --force >> /dev/null 2>&1
        docker container prune -f >> /dev/null 2>&1
        docker network prune -f >> /dev/null 2>&1

        # Connect and Join
        read -p "Master Node Address : " MASTER_ADDR
        read -p "Account Name : " ACCOUNT
        JOIN_COMMAND=`ssh $ACCOUNT@$MASTER_ADDR docker swarm join-token worker | grep join`
        JOIN_RESULT=`$JOIN_COMMAND`
        if [ "$?" != "0" ];
        then
            echo $JOIN_RESULT
        else
            echo $JOIN_RESULT
            echo "Docker Swarm Joined. (3/3)"
        fi 
    fi
else
    echo "================================="
    echo " Installation of MLAppDeploy"
    echo ""
    echo " Only support master node on WSL2"
    echo " And not support cluster set"
    echo " (Cannot join worker node)"
    echo "================================="
    echo Clear Swarm Setting...
    docker swarm leave --force >> /dev/null 2>&1
    docker container prune -f >> /dev/null 2>&1
    docker network prune -f >> /dev/null 2>&1
    docker network create --subnet 10.10.0.0/24 --gateway 10.10.0.1 -o com.docker.network.bridge.enable_icc=false -o com.docker.network.bridge.name=docker_gwbridge docker_gwbridge
    JOIN_RESULT=`docker swarm init $@ 1>/dev/null`
    if [ "$?" != "0" ];
    then
        echo $JOIN_RESULT
    else
        echo "Docker Swarm Initialized. (3/3)"
    fi
fi
   
