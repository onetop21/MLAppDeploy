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

function HostIP {
    if [[ `IsWSL2` == "1" ]]; then
       PS='(Get-NetIPConfiguration | Where-Object {
             $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -ne "Disconnected"
           }).IPv4Address.IPAddress' 
       IP=`powershell.exe -c $PS`
       echo "${IP%%[[:cntrl:]]}"
    else
        hostname -I | awk '{print $1}'
    fi
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

function InstallNVIDIAContainerRuntime {
    # https://github.com/NVIDIA/nvidia-container-runtime

    # Add the package repositories
    curl -s -L https://nvidia.github.io/nvidia-container-runtime/gpgkey | \
      sudo apt-key add -
    distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
    curl -s -L https://nvidia.github.io/nvidia-container-runtime/$distribution/nvidia-container-runtime.list | \
      sudo tee /etc/apt/sources.list.d/nvidia-container-runtime.list
    sudo apt-get update

    # Install nvidia-container-runtime
    sudo apt-get install -y nvidia-container-runtime
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

# Main Script
STEP=0
if [[ `IsWSL2` == '1' ]]; then
    MAX_STEP=3
    if [[ `IsInstalled docker` == '0' ]]; then
        ColorEcho INFO "Need to install Docker Desktop yourself on WSL2."
        ColorEcho INFO "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/wsl/"
        exit 1
    fi
    ColorEcho INFO "Ready to install docker on your WSL2."
else
    MAX_STEP=3

    GetPrivileged

    # Step 1: Install Requires
    PrintStep "Install Requires Utilities."
    RequiresFromApt jq

    # Step 3: Install Docker
    PrintStep "Install docker."
    DAEMON_JSON=/etc/docker/daemon.json
    UninstallOnSnapWithWarning docker
    if [[ `IsInstalled docker` == '0' ]]; then
        InstallDocker

        # Add user to docker group
        sudo adduser $USER docker
    fi

    if [[ `VerifyDocker` != "0" ]];
    then
        ColorEcho INFO "Need to reboot and retry install to continue install docker."
        exit 1
    fi

    # Step 4: Install NVIDIA Container Runtine
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
        fi
    fi
fi
