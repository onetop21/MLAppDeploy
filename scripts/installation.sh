#!/bin/bash
        
DAEMON_JSON="/etc/docker/daemon.json"

# Install Prerequires
echo "Install Prerequires."

# Check Docker status
IS_WSL2=`uname -r | grep microsoft-standard | wc -l`
DOCKER_INSTALLED=`which docker | wc -l`
if [ "$DOCKER_INSTALLED" != "0" ];
then
    echo "Installed Docker. (1/3)"
elif [ "$IS_WSL2" != "0" ];
then
    echo "Need to install Docker Desktop yourself on WSL2."
    exit
else
    echo "Install Docker. (1/3)"
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

    # Add user to docker group
    sudo adduser $USER docker
    sudo systemctl daemon-reload
    sudo systemctl restart docker
fi

VERIFY_DOCKER=`docker run -it --rm hello-world > /dev/null 2>&1; echo $?`
if [ "$VERIFY_DOCKER" != "0" ];
then
    echo "Need to reboot and retry install to continue install docker for MLAppDeploy."
    exit 0
fi

# Check Nvidia Driver status
NVIDIA_INSTALLED=`which nvidia-smi | wc -l`
if [ "$NVIDIA_INSTALLED" == "0" ];
then
    echo "Cannot find NVIDIA Graphic Card. (2/3)"
else
    RUNTIME_INSTALLED=`docker run -it --rm --runtime nvidia hello-world > /dev/null 2>&1; echo $?`
    if [ "$RUNTIME_INSTALLED" == "0" ];
    then
        echo "Installed NVidia Docker Runtime. (2/3)"
    else
        echo "Install NVidia Docker Runtime. (2/3)"
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

        # Read Daemon.json
        # Check nvidia runtime in daemon.json
        CONFIG=`sudo cat $DAEMON_JSON`
        if [ "`echo $CONFIG | jq '.runtimes.nvidia'`" == "null" ];
        then
            CONFIG=`echo $CONFIG | jq '.runtimes.nvidia2={"path":"nvidia-container-runtime", "runtimeArgs":[]}'`
        fi
        echo $CONFIG | jq . | sudo dd status=none of=$DAEMON_JSON
         
        # Test nvidia-smi with the latest official CUDA image
        docker run --runtime=nvidia --rm nvidia/cuda:9.0-base nvidia-smi

        # Enable GPU on docker swarm
        if [[ -z `sudo cat $DAEMON_JSON` ]]; then
            echo '{}' | sudo dd status=none of=$DAEMON_JSON
        fi
        GPU_IDS=`nvidia-smi -a | grep UUID | awk '{print substr($4,0,12)}'`
        CONFIG=`sudo cat $DAEMON_JSON | jq '."default-runtime"="nvidia"' | jq '."node-generic-resources"=[]'`
        for ID in $GPU_IDS; do
            CONFIG=`echo $CONFIG | jq '."node-generic-resources"=["gpu='$ID'"]+."node-generic-resources"'`
        done
        echo $CONFIG | jq . | sudo dd status=none of=$DAEMON_JSON

        # Advertise GPU device to swarm.
        sudo sed -i -e 's/#swarm-resource/swarm-resource/' /etc/nvidia-container-runtime/config.toml
    fi
fi

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
   
