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
    ColorEcho INFO "MLAppDeploy Environment Install Script"
    ColorEcho "$ $0 [-b,--bind master-address] [-r,--remote ssh-address]"
    ColorEcho "    -b, --bind   : Bind to master after install MLAppDeploy node. (Only node mode.)"
    ColorEcho "                   If not define *bind* option to install master mode."
    ColorEcho "    -r, --remote : Install MLAppDeploy Environment to Remote machine."
    ColorEcho "    -h, --help   : This page"
    exit 1
}

OPTIONS=$(getopt -o hr:b: --long help,remote:,bind: -- "$@")
[ $? -eq 0 ] || Usage
eval set -- "$OPTIONS"
while true; do
    case "$1" in
    -r|--remote) shift
        REMOTE=$1
        ;;
    -b|--bind) shift
        BIND=$1
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

if [[ ! -z "$REMOTE" ]]; then
    ARGS=
    if [[ ! -z "$BIND" ]]; then
        ARGS="-b $BIND"
    fi
    if [[ ! -z "$@" ]]; then
        ARGS="$ARGS -- $@"
    fi
    RemoteRun $REMOTE $ARGS
    exit 0
fi

#################################################################
# Main Code
#################################################################
function PrintStep {
    STEP=$((STEP+1))
    ColorEcho INFO "[$STEP/$MAX_STEP] $@"
}

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

function IsWSL2 {
    echo $(uname -r | grep microsoft-standard | wc -l)
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

function UninstallOnSnapWithWarning {
    if [[ `IsInstalled snap` != '0' ]]; then
        if [[ `snap list $1 >> /dev/null 2>&1 ; echo $?` == '0' ]]; then
            ColorEcho WARN "Need to remove $1 from Snapcraft."
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
    echo `sudo docker -H "" run -it --rm $@ hello-world > /dev/null 2>&1; echo $?`
}

function InstallNVIDIAContainerRuntime2008 {
    # https://github.com/NVIDIA/nvidia-container-runtime

    # Add the package repositories
    curl -s -L https://nvidia.github.io/nvidia-container-runtime/gpgkey | \
      sudo apt-key add-
    distribution=$(. /etc/os-release;echo $ID$VERSION)
    curl -s -L https://nvidia.github.io/nvidia-container-runtime/$distribution/nvidia-container-runtime.list | \
      sudo tee /etc/apt/sources.list.d/nvidia-container-runtime.list
    sudo apt-get update

    # Install nvidia-container-runtime
    sudo apt-get install -y nvidia-container-runtime
}

function InstallNVIDIAContainerRuntime2001 {
    # Deprecated Method Officialy

    # If you have nvidia-docker 1.0 installed: we need to remove it and all existing GPU containers
    docker -H "" volume ls -q -f driver=nvidia-docker | xargs -r -I{} -n1 sudo docker -H "" ps -q -a -f volume={} | xargs -r sudo docker -H "" rm -f
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
    echo `sudo docker -H "" run -it --rm --gpus hello-world > /dev/null 2>&1; echo $?`
}

function TouchDaemonJSON {
    # If no file
    #if [[ ! -f "$DAEMON_JSON" ]]; then
    if [[ ! `sudo test -f "$DAEMON_JSON";echo $?` ]]; then
        echo '{}' | sudo dd status=none of=$DAEMON_JSON
    elif [[ -z `sudo cat $DAEMON_JSON` ]]; then
        # If empty file
        echo '{}' | sudo dd status=none of=$DAEMON_JSON
    fi
}

function NVIDIAContainerRuntimeConfiguration {
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

function ClearDockerSwarmSetting {
    ColorEcho Clear Swarm Setting...
    sudo docker -H "" swarm leave --force >> /dev/null 2>&1
    sudo docker -H "" container prune -f >> /dev/null 2>&1
    sudo docker -H "" network prune -f >> /dev/null 2>&1
    sudo docker -H "" network create --subnet 10.10.0.0/24 --gateway 10.10.0.1 -o com.docker.network.bridge.enable_icc=false -o com.docker.network.bridge.name=docker_gwbridge docker_gwbridge
}

# Start Script
GetPrivileged

# Step 1: Install Requires
PrintStep Install Requires Utilities.
RequiresFromApt jq

# Step 2: Install Docker
PrintStep Install Docker.
if [[ `IsWSL2` == '1' ]]; then
    if [[ `IsInstalled docker` == '0' ]]; then
        ColorEcho INFO "Need to install Docker Desktop yourself on WSL2."
        ColorEcho INFO "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/wsl/"
        exit
    fi
else
    UninstallOnSnapWithWarning docker
    if [[ `IsInstalled docker` == '0' ]]; then
        InstallDocker

        # Add user to docker group
        sudo adduser $USER docker
    fi

    if [[ `VerifyDocker` != "0" ]];
    then
        ColorEcho INFO "Need to reboot and retry install to continue install docker for MLAppDeploy."
        exit 0
    fi
    TouchDaemonJSON
fi

PrintStep Install NVIDIA Container Runtime.
# Check Nvidia Driver status
if [ `IsInstalled nvidia-smi` == "0" ];
then
    ColorEcho WARN "Cannot find NVIDIA Graphic Card."
else
    if [ `VerifyDocker --gpus all` == "0" ];
    then
        ColorEcho INFO "Already installed NVIDIA container runtime."
    else
        ColorEcho INFO "Install NVIDIA container runtime."

        InstallNVIDIAContainerRuntime
        NVIDIAContainerRuntimeConfiguration
        UpdateGPUResources
        AdvertiseGPUonSwarm
    fi
fi

if [[ -z $BIND ]]; then
    if [[ `IsWSL2` == '0' ]]; then
        PrintStep Setup Master node.
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
    else
        PrintStep Setup Master node on WSL2.
        ColorEcho WARN "MLAppDeploy environment works only standalone on WSL2."
        ColorEcho WARN "Not support to bind other nodes."
    fi

    ClearDockerSwarmSetting
    JOIN_RESULT=`sudo docker -H "" swarm init $@ 1>/dev/null`
    if [ "$?" != "0" ];
    then
        ColorEcho WARN $JOIN_RESULT
    else
        ColorEcho "Docker Swarm Initialized."
    fi
else
    if [[ `IsWSL2` == '0' ]]; then
        PrintStep Setup Worker Node to $BIND

        ClearDockerSwarmSetting

        # Connect and Join
        JOIN_COMMAND=`ssh $BIND docker swarm join-token worker | grep join`
        JOIN_RESULT=`sudo $JOIN_COMMAND`
        if [ "$?" != "0" ];
        then
            ColorEcho WARN $JOIN_RESULT
        else
            ColorEcho INFO $JOIN_RESULT
            ColorEcho INFO "Docker Swarm Joined."
        fi
    else
        PrintStep Setup Worker Node to $BIND on WSL2
        ColorEcho WARN "Not support join to master node from WSL2 for stability."
    fi
fi 
ColorEcho Install Complete.
