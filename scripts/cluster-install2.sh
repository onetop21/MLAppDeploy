#!/bin/bash

PROJECT_NAME=MLAppDeploy
K3S_VERSION=v1.20.9+k3s1

if [ -f $0 ]; then
    WITH_BUILDER=1
fi

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


# Base Functions
function Prompt {
    local MESSAGE
    local DEFAULT
    local PASSWORD
    local REGEX
    local HIDDENDEF
    for ARG in "$@"; do
        local IDX=$((IDX+1))
        if [[ $ARG =~ ^([a-z]+:)*(.*)$ ]]; then
            case ${BASH_REMATCH[1]} in
            message:) MESSAGE=${BASH_REMATCH[2]};;
            default:) DEFAULT=${BASH_REMATCH[2]};;
            password:) PASSWORD=${BASH_REMATCH[2]};;
            regex:) REGEX=${BASH_REMATCH[2]};;
            *)
                case $IDX in
                1) MESSAGE=$ARG;;
                2) DEFAULT=$ARG;;
                esac
                ;;
            esac
        fi
    done
    if [ ${DEFAULT:0:1} == "@" ]
    then
        DEFAULT=${DEFAULT:1}
        HIDDENDEF=1
    fi
    while [[ ! "$RESULT" =~ $REGEX ]]
    do 
        read -p "$MESSAGE$([ ! $HIDDENDEF ] && [ $DEFAULT ] && echo " [$DEFAULT]"): " $([ $PASSWORD ] && echo -s) -e RESULT
        [ -z $RESULT ] && RESULT=$DEFAULT
    done
    echo ${RESULT,,}
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
    which $1 >> /dev/null 2>&1
}

function IsWSL2 {
    [ $(uname -r | grep microsoft-standard | wc -l) -eq 0 ] && return 1
    return 0
}

function HostIP {
    if IsWSL2
    then
       PS='(Get-NetIPConfiguration | Where-Object {
             $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -ne "Disconnected"
           }).IPv4Address.IPAddress' 
       IP=$(powershell.exe -c $PS)
       echo "${IP%%[[:cntrl:]]}"
    else
        hostname -I | awk '{print $1}'
    fi
}

function RequiresFromApt {
    printf "Check requires [$1]... "
    if ! IsInstalled $1
    then
        ColorEcho WARN Need to install $1.
        sudo apt install -y $1
    else
        ColorEcho DEBUG Okay
    fi
}

function UninstallOnSnapWithWarning {
    if IsInstalled snap
    then
        if [[ $(snap list $1 >> /dev/null 2>&1 ; echo $?) == '0' ]]; then
            ColorEcho WARN "Need to remove $1 from Snapcraft."
            read -n1 -r -p  "If you want to stop installation, Press CTRL+C to break, otherwise any key to continue."
            sudo snap remove --purge $1

            # Clean : https://docs.docker.com/engine/install/ubuntu/#uninstall-docker-engine
            #sudo apt-get purge docker-ce docker-ce-cli containerd.io
            #sudo rm -rf /var/lib/docker
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
    sudo docker run -it --rm $@ hello-world >> /dev/null 2>&1
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

function GetContainerdNVIDIATemplateFile {
    #sudo wget https://raw.githubusercontent.com/baidu/ote-stack/master/deployments/k3s/config.toml.tmpl -O /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
    sudo mkdir -p /var/lib/rancher/k3s/agent/etc/containerd
    if [ -f nvidia-containerd.config.toml.tmpl ]
    then
        sudo cp nvidia-containerd.config.toml.tmpl /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
    else
        sudo wget https://raw.githubusercontent.com/onetop21/MLAppDeploy/master/scripts/nvidia-containerd.config.toml.tmpl -O /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
    fi
}

function WithDocker {
    [ $CALLED_WITHDOCKER ] && return 0
    CALLED_WITHDOCKER=1

    if ! VerifyDocker
    then
        printf "Install Docker... "
        #UninstallOnSnapWithWarning docker
        if ! IsInstalled docker
        then
            InstallDocker

            # Add user to docker group
            sudo adduser $USER docker
        fi

        if ! VerifyDocker
        then
            ColorEcho WARN "Failed to operate docker."
            sudo systemctl status docker.service
            ColorEcho ERROR Failed
            exit 1
        fi
        ColorEcho DEBUG Succeeded
    fi
}

function IsInstalledCluster {
    kubectl get node >> /dev/null 2>&1
}

function IsDeployed {
    local KIND=${1:-pod}; shift
    local COUNT=0
    for LABEL in $@
    do
        COUNT=$((COUNT+$(kubectl get -A $KIND -l $LABEL -o name | wc -l)))
    done
    [ "$COUNT" -eq 0 ] && return 1
    return 0
}

function HasHelmRepo {
    VALUE=$1
    COUNT_NAME=$(helm repo list -o json | jq .[].name -r | grep -e ^${VALUE}$ | wc -l)
    COUNT_REPO=$(helm repo list -o json | jq .[].url -r | grep -e ^${VALUE}$ | wc -l)
    COUNT=$((COUNT_NAME+COUNT_REPO))
    [ $COUNT -ne 0 ] && return 0 || return 1
}

# Usage/Help
function UsageHeader {
    ColorEcho INFO "MLAppDeploy Environment Installer (based k3s)"
    if [ $1 ]; then
        ColorEcho WARN "Usage"
        ColorEcho      "    $ $0 $1 [ARGS...]"
    fi
}

function MainUsage {
    if [ $WITH_BUILDER ]; then
        MainUsage2
    else
        MainUsage1
    fi
}

function MainUsage1 {
    UsageHeader
    ColorEcho WARN "Commands"
    ColorEcho      "    master     : Install MLAppDeploy environments as master node."
    ColorEcho      "    worker     : Install MLAppDeploy environments as worker node and join with master node."
    ColorEcho      "    uninstall  : Uninstall MLAppDeploy environments."
    ColorEcho      "    deploy     : Deploy MLAppDeploy service with requires."
    ColorEcho      "    status     : Show MLAppDeploy environment status."
    ColorEcho      "    help       : Print help message."
    exit 1
}

function MainUsage2 {
    UsageHeader
    ColorEcho WARN "Commands"
    ColorEcho      "    master     : Install MLAppDeploy environments as master node."
    ColorEcho      "    worker     : Install MLAppDeploy environments as worker node and join with master node."
    ColorEcho      "    uninstall  : Uninstall MLAppDeploy environments."
    ColorEcho      "    deploy     : Deploy MLAppDeploy service."
    ColorEcho      "    build      : Build MLAppDeploy service."
    ColorEcho      "    status     : Show MLAppDeploy environment status."
    ColorEcho      "    help       : Print help message."
    exit 1
}

function MasterUsage {
    UsageHeader master
    ColorEcho WARN "Arguments"
    ColorEcho      "    -r, --with-registry           : Install container registry (requires docker)."
    #ColorEcho      "    -d, --with-datastore          : Install datastores(MinIO, MongoDB) for MLAppDeploy (requires docker)."
    ColorEcho      "    -h, --help                    : This page"
    exit 1
}

function WorkerUsage {
    UsageHeader worker
    ColorEcho WARN "Arguments"
    ColorEcho      "    -i, --master-ip=[ADDRESS]     : IP address of master node to join."
    ColorEcho      "    -u, --master-user=[USERNAME]  : Username of master node to join."
    ColorEcho      "                                    (Default: $USER)"
    ColorEcho      "    -h, --help                    : This page"
    exit 1
}

function BuildUsage {
    UsageHeader build
    ColorEcho WARN "Arguments"
    ColorEcho      "        --registry=[REPO/ORG]     : Target to deploy service image. (Required)"
    ColorEcho      "        --name=[SERVICENAME]      : Image name of the service (default: service)"
    ColorEcho      "    -h, --help                    : This page"
    exit 1
}

function DeployUsage {
    UsageHeader deploy
    ColorEcho WARN "Arguments"
    ColorEcho      "        --registry=[REPO/ORG]     : Change target to pull service image."
    ColorEcho      "                                    (Default: ghcr.io/onetop21)"
    ColorEcho      "        --name=[SERVICENAME]      : Image name of the service (default: service)"
    ColorEcho      "        --ingress=[LOADBALANCER|NODEPORT]"
    ColorEcho      "                                  : Deploy ingress with type to LoadBalancer or NodePort."
    ColorEcho      "                                    (Default: LOADBALANCER)"
    ColorEcho      "        --monitoring              : Deploy prometheus stack for monitoring cluster."
    ColorEcho      "        --set=[key=value]         : Bypass arguments with set option to helm commands."
    ColorEcho      "    -b, --beta                    : Deploy service as beta mode. (prefix: /beta)"
    #ColorEcho      "        --config=[PATH]           : Set service configure file. (Not yet)"
    ColorEcho      "    -r, --reset                   : Reset MLAppDeploy namespace."
    ColorEcho      "    -h, --help                    : This page"
    exit 1
}

# Base Command
eval set -- "$@"
while [ $# -ne 0 ]; do
    case "$1" in
    master)
        MASTER=1
        shift
        break
        ;;
    worker)
        WORKER=1
        shift
        break
        ;;
    uninstall)
        UNINSTALL=1
        break
        ;;
    deploy)
        DEPLOY=1
        shift
        break
        ;;
    build)
        if [ $WITH_BUILDER ]; then
            BUILD=1
            shift
            break
        fi
        ;;
    status)
        STATUS=1
        shift
        break
        ;;
    esac
    shift
done

if [ $MASTER ]; then
    #OPTIONS=$(getopt -o rdh --long with-registry,with-datastore,help -- "$@")
    OPTIONS=$(getopt -o rh --long with-registry,help -- "$@")
    [ $? -eq 0 ] || MasterUsage
    eval set -- "$OPTIONS"
    while true; do
        case "$1" in
        -r|--with-registry)
            REGISTRY=1
            WITH_DOCKER=1
            ;;
        -d|--with_datastore)
            DATASTORE=1
            WITH_DOCKER=1
            ;;
        -h|--help)
            MasterUsage
            ;;
        --)
            shift
            break
            ;;
        esac
        shift
    done

elif [ $WORKER ]; then
    MASTER_USER=$USER
    OPTIONS=$(getopt -o i:u:h --long master-ip:,master-user:,help -- "$@")
    [ $? -eq 0 ] || WorkerUsage
    eval set -- "$OPTIONS"
    while true; do
        case "$1" in
        -i|--master-ip) shift
            MASTER_IP=$1
            ;;
        -u|--master-user) shift
            MASTER_USER=$1
            ;;
        -h|--help)
            WorkerUsage
            ;;
        --)
            shift
            break
            ;;
        esac
        shift
    done

    if [ -z $MASTER_IP ]; then
        ColorEcho ERROR "Need an argument '--master-ip [IP ADDRESS]', to install environments as worker node."
        exit 1
    fi

elif [ $BUILD ]; then
    OPTIONS=$(getopt -o f:h --long registry:,name:,help -- "$@")
    SERVICE_NAME=service
    [ $? -eq 0 ] || BuildUsage
    eval set -- "$OPTIONS"
    while true; do
        case "$1" in
        --registry) shift
            REGISTRY_ADDR=$1
            ;;
        -h|--help)
            BuildUsage
            ;;
        --name) shift
            SERVICE_NAME=$1
            ;;
        --)
            shift
            break
            ;;
        esac
        shift
    done
    if [ ! $REGISTRY_ADDR ]; then
        ColorEcho ERROR "Required to build with target registry(--registry)."
        BuildUsage
        exit 1
    fi

elif [ $DEPLOY ]; then
    LOADBALANCER=1  # Default
    declare -A HELM_ARGS_OVERRIDE
    REGISTRY_ADDR=ghcr.io/onetop21 # ref, https://github.com/onetop21/MLAppDeploy
    SERVICE_NAME=service
    OPTIONS=$(getopt -o brh --long registry:,name,ingress:,monitoring,set:,beta,config:,reset,help -- "$@")
    [ $? -eq 0 ] || DeployUsage
    eval set -- "$OPTIONS"
    while true; do
        case "$1" in
        --registry) shift
            REGISTRY_ADDR=$1
            ;;
        --name) shift
            SERVICE_NAME=$1
            ;;
        --ingress) shift
            INGRESS=1
            case "${1,,}" in
            lb|loadbalancer)
                LOADBALANCER=1
                ;;
            np|nodeport)
                unset LOADBALANCER
                ;;
            *)
                [ ${1:0:2} == "--" ] && continue \
                    || ColorEcho WARN "Not support ingress type [$1]."
                ;;
            esac
            ;;
        --monitoring)
            MONITORING=1
            ;;
        --set) shift
            eval "KV=($(echo $1 | tr '=' ' '))"
            HELM_ARGS_OVERRIDE[${KV[0]}]=${KV[1]}
            ;;
        -b|--beta)
            BETA=1
            ;;
        --config) shift
            ColorEcho ERROR "Config option is not support yet."
            exit 1
            ;;
        -r|--reset)
            RESET=1
            ;;
        -h|--help)
            DeployUsage
            ;;
        --)
            shift
            break
            ;;
        esac
        shift
    done

elif [ $STATUS ]; then
    :

elif [ $UNINSTALL ]; then
    :

else
    MainUsage
fi

# Main Script
STEP=0
if [ $MASTER ] || [ $WORKER ]
then
    if IsWSL2
    then
        MAX_STEP=3

        if ! IsInstalled docker
        then
            ColorEcho INFO "Need to install Docker Desktop yourself on WSL2."
            ColorEcho INFO "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/wsl/"
            exit 1
        fi
        if IsInstalled kubectl
        then
            ColorEcho INFO "Need to install kubernetes on Docker Desktop yourself."
            ColorEcho INFO "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/#kubernetes"
            exit 1
        fi
        if IsInstalledCluster
        then
            ColorEcho WARN "Check kubernetes status or kubeconfig."
            exit 1
        fi
        ColorEcho INFO "Ready to install MLAppDeploy on your WSL2."
    else
        GetPrivileged
        MAX_STEP=$(( 2 + REGISTRY + DATASTORE ))
        if [ $REGISTRY ]
        then
            WithDocker
            PrintStep Install Registry
            RUNNING_CONTAINER=$(sudo docker ps -q -f label=mlappdeploy.type=registry | wc -l)
            PORT_CONFLICTED_CONTAINERS=$(sudo docker ps -q -f publish=5000 --format {{.Names}})
            PORT_CONFLICTED_PROCESSES=$(sudo netstat -ap | grep -e :5000[0-9\ .:*]*LISTEN | awk '{print $7}')
            if [ $RUNNING_CONTAINER -ne 0 ]; then
                ColorEcho DEBUG "Already Installed."
            elif [ $PORT_CONFLICTED_CONTAINERS ]; then
                ColorEcho WARN "Failed to install.\nAlready use 5000/tcp by [$PORT_CONFLICTED_CONTAINERS] container."
            elif [ $PORT_CONFLICTED_PROCESSES ]; then
                ColorEcho WARN "Failed to install.\nAlready use 5000/tcp by [$PORT_CONFLICTED_PROCESSES] process."
            else
                sudo docker run -d -p 5000:5000 --restart=always --name mlad-registry -v registry-data:/var/lib/registry \
                    --label mlappdeploy.type=registry \
                    registry:2
            fi
        fi
        if [ $DATASTORE ]
        then
            WithDocker
            PrintStep Install Datastores\(MinIO, MongoDB\)

            #read -p "Type Access Key of MinIO (Default: MLAPPDEPLOY) : " ACCESS_KEY
            #export ACCESS_KEY
            #read -p "Type Secret Key of MinIO (Default: MLAPPDEPLOY) : " SECRET_KEY
            #export SECRET_KEY
            sudo docker run -d -p 27017:27017 --restart=always --name mlad-mongodb -v mongo-data:/data/db \
                --label mlappdeploy.type=datastore --label mlappdeploy.datastore=mongodb \
                mongo

            read -p "Type Access Key of MinIO : " -ei MLAPPDEPLOY ACCESS_KEY
            export ACCESS_KEY
            read -p "Type Secret Key of MinIO : " -ei MLAPPDEPLOY SECRET_KEY
            export SECRET_KEY
            sudo docker run -d -p 9000:9000 --restart=always --name mlad-minio -v minio-data:/data \
                --label mlappdeploy.type=datastore --label mlappdeploy.datastore=minio \
                -e MINIO_ACCESS_KEY $ACCESS_KEY -e MINIO_SECRET_KEY $SECRET_KEY \
                minio/minio server /data
        fi

        # Step 1: Install NVIDIA Container Runtine
        PrintStep Install NVIDIA Container Runtime.
        # Check Nvidia Driver status
        if ! IsInstalled nvidia-smi
        then
            ColorEcho WARN "Cannot find NVIDIA Graphic Card."
        else
            if IsInstalled nvidia-container-runtime
            then
                ColorEcho INFO "Already installed NVIDIA container runtime."
            else
                ColorEcho INFO "Install NVIDIA container runtime."

                InstallNVIDIAContainerRuntime

                if IsInstalled nvidia-container-runtime
                then
                    ColorEcho INFO "Completed installation NVIDIA container runtime."
                else
                    ColorEcho ERROR "Failed to install NVIDIA container runtime."
                    ColorEcho ERROR "Pass this installation..." 
                    ColorEcho ERROR "If you want to use GPU on node, install NVIDIA container runtime at this node manually."
                fi
            fi
        fi

        # Step 4: Install Kubernetes
        PrintStep "Install Kubernetes."
        if ! IsInstalledCluster
        then
            if ! IsInstalled k3sup
            then
                pushd /tmp
                curl -sLS https://get.k3sup.dev | sh
                sudo install k3sup /usr/local/bin/
                popd
            fi
            if ! IsInstalled k3s
            then
                IsInstalled nvidia-container-runtime && GetContainerdNVIDIATemplateFile
                if [ $MASTER ]
                then
                    # Add priviledged for getting token
                    ColorEcho INFO "Set priviledge for getting token by worker."
                    echo "$USER ALL=NOPASSWD: $(which cat)" | sudo tee /etc/sudoers.d/$USER-k3s-token >> /dev/null 2>&1
                    # Create registries.yaml for insecure private registry
                    RUNNING_CONTAINER=$(sudo docker ps -q -f label=mlappdeploy.type=registry | wc -l)
                    MASTER_IP=$(HostIP)
                    if [ $RUNNING_CONTAINER ]; then
                        ColorEcho "Register insecure registry."
                        sudo mkdir -p /etc/rancher/k3s/
                        echo -e "mirror:\n  $MASTER_IP:5000:\n    endpoint:\n      - http://$MASTER_IP:5000" | sudo tee /etc/rancher/k3s/registries.yaml
                    fi

                    # Install k3s server
                    k3sup install --local --local-path ~/.kube/config --k3s-extra-args \
                        "--disable traefik --write-kubeconfig-mode 644" \
                        --cluster --k3s-version $K3S_VERSION
                elif [ $WORKER ]; then
                    # Add priviledged for getting token
                    ColorEcho INFO "Set priviledge for getting token by worker."
                    echo "$USER ALL=NOPASSWD: ALL" | sudo tee /etc/sudoers.d/$USER-k3s-token >> /dev/null 2>&1
                    cat /dev/zero | ssh-keygen -q -N "" >> /dev/null 2>&1
                    ssh-copy-id -o 'UserKnownHostsFile=/dev/null' -o 'StrictHostKeyChecking=no' -f $USER@127.0.0.1 >> /dev/null 2>&1
                    ssh-copy-id -o 'UserKnownHostsFile=/dev/null' -o 'StrictHostKeyChecking=no' -f $MASTER_USER@$MASTER_IP >> /dev/null 2>&1
                    # Create registries.yaml for insecure private registry
                    if [ $(curl -s -o /dev/null -w "%{http_code}" http://$MASTER_IP:5000/v2/_catalog) -eq "200" ]; then
                        ColorEcho "Register insecure registry."
                        sudo mkdir -p /etc/rancher/k3s/
                        echo -e "mirror:\n  $MASTER_IP:5000:\n    endpoint:\n      - http://$MASTER_IP:5000" | sudo tee /etc/rancher/k3s/registries.yaml
                    fi
                    # Install k3s agent
                    k3sup join --server-ip $MASTER_IP --user $MASTER_USER --ip 127.0.0.1 --user $USER --k3s-version $K3S_VERSION
                    ColorEcho INFO "Finish join worker node with $MASTER_IP."
                else
                    ColorEcho ERROR "Failed to install kubernetes. You need to run with master or worker command."
                fi
            fi
            export KUBECONFIG=$HOME/.kube/config
            chmod 600 $HOME/.kube/config
            kubectl config set-context default
        else
            ColorEcho "Already installed kubernetes."
        fi
    fi
elif [ $UNINSTALL ]
then
    if IsWSL2
    then
        ColorEcho ERROR "Cannot support remove kubernetes on WSL2."
        exit 0
    fi
    
    GetPrivileged
    MAX_STEP=1
    PrintStep "Uninstall Kubernetes."
    if [[ $(which k3s-uninstall.sh >> /dev/null 2>&1; echo $?) == "0" ]]; then
        ColorEcho INFO "Uninstall master node."
        sudo k3s-uninstall.sh 
    elif [[ $(which k3s-agent-uninstall.sh >> /dev/null 2>&1; echo $?) == "0" ]]; then
        ColorEcho INFO "Uninstall worker node."
        sudo k3s-agent-uninstall.sh 
    else
        if [[ $(kubectl version >> /dev/null 2>&1; echo $?) == "0" ]]; then
            ColorEcho ERROR "No have permission to remove kubernetes."
        else
            ColorEcho INFO "Already removed kubernetes."
        fi
    fi
elif [ $BUILD ]
then
    GetPrivileged
    MAX_STEP=3

    WithDocker
    IMAGE_NAME=$REGISTRY_ADDR/mlappdeploy/$SERVICE_NAME
    # Step 5: Build Service Package
    PrintStep "Build Service Image."
    ColorEcho INFO "Build from Local."
    DOCKER_BUILDKIT=0 sudo docker build -t $IMAGE_NAME -f Dockerfile ..
    VERSION=$(sudo docker run -it --rm --entrypoint "mlad" $IMAGE_NAME --version | awk '{print $3}' | tr -d '\r')
    TAGGED_IMAGE=$IMAGE_NAME:$VERSION
    PrintStep "Tag Version to Image [$VERSION]."
    docker tag $IMAGE_NAME $TAGGED_IMAGE
    PrintStep "Push Image to Registry [$REGISTRY_ADDR]."
    docker push $TAGGED_IMAGE
    docker push $IMAGE_NAME:latest --quiet
    if [ $? -ne 0 ]; then
        ColorEcho ERROR 'Failed to upload image. Please check your authentication.'
        ColorEcho ERROR "  $ docker login $(echo $REGISTRY_ADDR | awk -F '/' '{print $1}')"
    fi

elif [ $DEPLOY ]
then
    GetPrivileged
    
    INSTANCE=${PROJECT_NAME,,}
    NAMESPACE=${PROJECT_NAME,,}

    if ! IsInstalledCluster
    then
        ColorEcho ERROR "Need to install MLAppDeploy environment as master first."
        ColorEcho ERROR "  $ $0 master [ARGS...]."
        exit 1
    fi

    (! IsInstalled helm) && HELM=1
    [ $INGRESS ] && (IsDeployed deploy app.kubernetes.io/name=ingress-nginx app=ingress-nginx) && unset INGRESS
    [ $MONITORING ] && (IsDeployed deploy app=kube-prometheus-stack-operator) && unset MONITORING
    (! IsDeployed ds app.kubernetes.io/name=nvidia-device-plugin name=nvidia-device-plugin-ds app=nvidia-device-plugin-daemonset ||
     ! IsDeployed pod app.kubernetes.io/name=nvidia-device-plugin name=nvidia-device-plugin-ds app=nvidia-device-plugin-daemonset) && NVDP=1
    (! IsDeployed ds app.kubernetes.io/name=node-feature-discovery app=nfd) && NFD=1
    (! IsDeployed ds app.kubernetes.io/name=gpu-feature-discovery app=gpu-feature-discovery) && GFD=1
    (! IsDeployed ds app.kubernetes.io/component=dcgm-exporter app=nvidia-dcgm-exporter) && DCGM=1
    (! IsDeployed deploy k8s-app=metrics-server) && METRICS=1

    # Process Helm options
    declare -A HELM_ARGS
    [ $NVDP ] && {
        [ "${HELM_ARGS_OVERRIDE[nvidia-device-plugine.enabled]}" == "false" ] && \
            HELM_ARGS[nvidia-device-plugin.enabled]=false || HELM_ARGS[nvidia-device-plugin.enabled]=true
    } || {
        HELM_ARGS[nvidia-device-plugin.enabled]=false
        ColorEcho WARN 'Already installed NVIDIA device plugin.'
    }
    [ $NFD ] && {
        [ "${HELM_ARGS_OVERRIDE[gpu-feature-discovery.nfd.deploy]}" == "false" ] && \
            HELM_ARGS[gpu-feature-discovery.nfd.deploy]=false || HELM_ARGS[gpu-feature-discovery.nfd.deploy]=true
    } || {
        HELM_ARGS[gpu-feature-discovery.nfd.deploy]=false
        ColorEcho WARN 'Already installed node feature discovery.'
    }
    [ $GFD ] && {
        [ "${HELM_ARGS_OVERRIDE[gpu-feature-discovery.enabled]}" == "false" ] && \
            HELM_ARGS[gpu-feature-discovery.enabled]=false || HELM_ARGS[gpu-feature-discovery.enabled]=true
    } || {
        HELM_ARGS[gpu-feature-discovery.enabled]=false
        ColorEcho WARN 'Already installed gpu feature discovery.'
    }
    [ $DCGM ] && {
        [ "${HELM_ARGS_OVERRIDE[dcgm-exporter.enabled]}" == "false" ] && \
            HELM_ARGS[dcgm-exporter.enabled]=false || HELM_ARGS[dcgm-exporter.enabled]=true
    } || {
        HELM_ARGS[dcgm-exporter.enabled]=false
        ColorEcho WARN 'Already installed data center gpu monitor.'
    }

    # Merge Helm Args
    for KEY in ${!HELM_ARGS_OVERRIDE[@]}
    do
        HELM_ARGS[$KEY]=${HELM_ARGS_OVERRIDE[$KEY]}
    done

    MAX_STEP=$((3+HELM+METRICS+INGRESS+MONITORING))

    # Install Helm
    [ $HELM ] && (
        PrintStep "Install Helm."
        curl -s https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
    )

    # Install Metrics Server
    [ $METRICS ] && (
        PrintStep "Install Metrics Server."
        ! HasHelmRepo metrics-server && helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
        helm repo update
        helm install --set 'args={--kubelet-insecure-tls}' -n kube-system metrics-server metrics-server/metrics-server
    )

    # Install Ingress-NGINX
    if [ $INGRESS ]
    then
        PrintStep "Install Ingress-NGINX."
        ! HasHelmRepo ingress-nginx && helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
        helm repo update
        [ $LOADBALANCER ] && \
            helm install ingress-nginx ingress-nginx/ingress-nginx --create-namespace -n ingress-nginx || \
            helm install ingress-nginx ingress-nginx/ingress-nginx --create-namespace -n ingress-nginx --set controller.service.type=NodePort
        ColorEcho INFO "Wait few minutes for available ingress controller."
        kubectl wait --for=condition=available --timeout=600s -n ingress-nginx deployment.apps/ingress-nginx-controller || \
            ColorEcho ERROR "Timeout waiting for ingress controller."
    fi

    # Install Prometheus Stack
    [ $MONITORING ] && (
        PrintStep "Install Prometheus Stack."
        ! HasHelmRepo prometheus-community && helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
        helm repo update
        helm install prometheus-stack prometheus-community/kube-prometheus-stack --create-namespace -n monitoring \
            --set grafana.ingress.enabled=true \
            --set grafana.ingress.path=/grafana \
            --set grafana.'grafana\.ini'.server.root_url='%(protocol)s://%(domain)s:%(http_port)s/grafana' \
            --set grafana.'grafana\.ini'.server.serve_from_sub_path=true \
            --set prometheus.ingress.enabled=true \
            --set prometheus.ingress.paths={/prometheus} \
            --set prometheus.ingress.pathType=Prefix \
            --set prometheus.prometheusSpec.routePrefix=/prometheus \
            --set prometheus.prometheusSpec.externalUrl=/prometheus \
            --set alertmanager.ingress.enabled=true \
            --set alertmanager.ingress.annotations.'nginx\.ingress\.kubernetes\.io/rewrite-target'='/$2' \
            --set alertmanager.ingress.paths='{/alertmanager(/|$)(.*)}'
    )

    # Find dcgm-exporter.serviceMonitor.additionalLabels and dcgm-exporter.serviceMonitor.namespace values
    [ $DCGM ] && IsDeployed deploy app=kube-prometheus-stack-operator && {
        # dcgm-exporter.serviceMonitor.additionalLabels
        JSON=$(kubectl get prometheus -A -l app=kube-prometheus-stack-prometheus -o jsonpath="{.items[*].spec.serviceMonitorSelector.matchLabels}")
        KEYS=$(echo $JSON | jq keys[] -r)
        for KEY in $KEYS
        do
            HELM_ARGS[dcgm-exporter.serviceMonitor.additionalLabels.$KEY]=$(echo $JSON | jq .$KEY -r)
        done

        # dcgm-exporter.serviceMonitor.namespace
        JSON_NAMES=$(kubectl get prometheus -A -l app=kube-prometheus-stack-prometheus -o jsonpath="{.items[*].spec.serviceMonitorNamespaceSelector.matchNames}")
        NAMES_COUNT=$(echo $JSON_NAMES | jq length)
        [ ${NAMES_COUNT:-0} -gt 0 ] && {
            HELM_ARGS[dcgm-exporter.serviceMonitor.namespace]=$(echo $JSON_NAMES | jq .[0] -r)
        }
    }

    PrintStep "Deploy MLAppDeploy Service."
    ! HasHelmRepo mlappdeploy && helm repo add mlappdeploy https://onetop21.github.io/MLAppDeploy/charts
    helm repo update

    SELECTOR=app.kubernetes.io/instance=$INSTANCE,app.kubernetes.io/name=$SERVICE_NAME
    IMAGE_NAME=$REGISTRY_ADDR/mlappdeploy/$SERVICE_NAME
    VERSION=$(sudo docker run -it --rm --entrypoint "mlad" $IMAGE_NAME --version | awk '{print $3}' | tr -d '\r')
    HELM_ARGS[image.repository]=$IMAGE_NAME
    HELM_ARGS[image.tag]=$VERSION

    if [ $BETA ]
    then
        SELECTOR+=',app.kubernetes.io/beta'
        INSTANCE+='-beta'
        HELM_ARGS[additionalLabels.app\.kubernetes\.io/beta]=true
        HELM_ARGS[ingress.annotations.'nginx\.ingress\.kubernetes\.io/rewrite-target']='/$2'
        HELM_ARGS[ingress.host[0].path[0].path]='/beta(/|$)(.*)'
        HELM_ARGS[env.ROOT_PATH]='/beta'
        HELM_ARGS[image.tag]=latest
    fi
    (IsDeployed deploy $SELECTOR) && ROLLOUT=1

    # Generate Options
    for KEY in ${!HELM_ARGS[@]}
    do
        HELM_OPTIONS+="--set $KEY=${HELM_ARGS[$KEY]} "
    done

    if [ $RESET ]
    then
        ColorEcho "Remove installed previous service."
        (   # Scope
            NAMESPACE=$(kubectl get -A deploy -l $SELECTOR -o jsonpath="{.items[*].metadata.annotations.meta\.helm\.sh/release-namespace}")
            [ $NAMESPACE ] && helm uninstall -n $NAMESPACE $INSTANCE
        )
    fi

    ColorEcho "Deploy MLAppDeploy service."
    if [ $ROLLOUT ]
    then
        helm update $INSTANCE mlappdeploy/api-server -n $NAMESPACE --set imagePullSecrets[0].name=regcred $HELM_OPTIONS
    else
        helm install $INSTANCE mlappdeploy/api-server --create-namespace -n $NAMESPACE --set imagePullSecrets[0].name=regcred $HELM_OPTIONS
    fi
    kubectl create secret -n $NAMESPACE generic regcred --from-file=.dockerconfigjson=$HOME/.docker/config.json --type=kubernetes.io/dockerconfigjson \
        --save-config --dry-run=client -o yaml | kubectl apply -f -
fi