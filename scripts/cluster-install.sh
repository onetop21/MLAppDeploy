#!/bin/bash

#if [ -f $0 ] && [ -f MLADService-Dockerfile ]; then
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
    ColorEcho      "    deploy     : Deploy MLAppDeploy service."
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
    ColorEcho      "    build      : Build MLAppDeploy service."
    ColorEcho      "    deploy     : Deploy MLAppDeploy service."
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
    ColorEcho      "        --registry=[REPO/ORG]     : Change target to deploy and pulling service image."
    ColorEcho      "                                    (Default: ghcr.io/onetop21)"
    ColorEcho      "    -f, --build-from=(git, local) : Choose source path to build. (Default: git)"
    ColorEcho      "    -h, --help                    : This page"
    exit 1
}

function DeployUsage {
    UsageHeader deploy
    ColorEcho WARN "Arguments"
    ColorEcho      "        --registry=[REPO/ORG]     : Change target to deploy and pulling service image."
    ColorEcho      "                                    (Default: ghcr.io/onetop21)"
    ColorEcho      "        --ingress=[LB|LOADBALANCER/NP|NODEPORT]"
    ColorEcho      "                                  : Set ingress type to LoadBalancer or NodePort."
    ColorEcho      "                                    (Default: NodePort)"
    ColorEcho      "    -b, --beta                    : Deploy service beta mode. (prefix: /beta)"
    ColorEcho      "        --config=[PATH]           : Set service configure file. (Not yet)"
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
    build)
        if [ $WITH_BUILDER ]; then
            BUILD=1
            shift
            break
        fi
        ;;
    deploy)
        DEPLOY=1
        shift
        break
        ;;
    status)
        STATUS=1
        shift
        break
        ;;
    uninstall)
        UNINSTALL=1
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
    REGISTRY_ADDR=ghcr.io/onetop21 # ref, https://github.com/onetop21/MLAppDeploy
    OPTIONS=$(getopt -o f:h --long registry:,build-from:,help -- "$@")
    [ $? -eq 0 ] || BuildUsage
    eval set -- "$OPTIONS"
    while true; do
        case "$1" in
        --registry) shift
            REGISTRY_ADDR=$1
            ;;
        -f|--build-from) shift
            case "$1" in
            local|git)
                BUILD_FROM=$1
                ;;
            *)
                ColorEcho ERROR "Only support value 'local' or 'git'."
                exit 1
                ;;
            esac
            ;;
        -h|--help)
            BuildUsage
            ;;
        --)
            shift
            break
            ;;
        esac
        shift
    done

elif [ $DEPLOY ]; then
    REGISTRY_ADDR=ghcr.io/onetop21 # ref, https://github.com/onetop21/MLAppDeploy
    OPTIONS=$(getopt -o brh --long registry:,ingress:,beta,config:,reset,help -- "$@")
    [ $? -eq 0 ] || DeployUsage
    eval set -- "$OPTIONS"
    while true; do
        case "$1" in
        --registry) shift
            REGISTRY_ADDR=$1
            ;;
        --ingress) shift
            INGRESS=1
            case "$(1,,)" in
            lb|loadbalancer)
                LOADBALANCER=1
                ;;
            np|nodeport)
                NODEPORT=1
                ;;
            *)
                ColorEcho WARN "Not support ingress type [$1]."
                ;;
            esac
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

# Base Functions
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

function GetContainerdNVIDIATemplateFile {
    #sudo wget https://raw.githubusercontent.com/baidu/ote-stack/master/deployments/k3s/config.toml.tmpl -O /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
    sudo mkdir -p /var/lib/rancher/k3s/agent/etc/containerd
    if [ -f nvidia-containerd.config.toml.tmpl ]; then
        sudo cp nvidia-containerd.config.toml.tmpl /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
    else
        sudo wget https://raw.githubusercontent.com/onetop21/MLAppDeploy/refactoring/scripts/nvidia-containerd.config.toml.tmpl -O /var/lib/rancher/k3s/agent/etc/containerd/config.toml.tmpl
    fi
}

# Main Script
STEP=0
if [ $MASTER ] || [ $WORKER ]; then
    if [[ `IsWSL2` == '1' ]]; then
        MAX_STEP=3
        if [[ "$UNINSTALL" == "1" ]]; then
            ColorEcho ERROR "Cannot support remove kubernetes on WSL2."
            exit 0
        fi

        if [[ `IsInstalled docker` == '0' ]]; then
            ColorEcho INFO "Need to install Docker Desktop yourself on WSL2."
            ColorEcho INFO "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/wsl/"
            exit 1
        fi
        if [[ `IsInstalled kubectl` == '0' ]]; then
            ColorEcho INFO "Need to install kubernetes on Docker Desktop yourself."
            ColorEcho INFO "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/#kubernetes"
            exit 1
        fi
        if [[ `kubectl get node 2>&1 >> /dev/null; echo $?` == "1" ]]; then
            ColorEcho WARN "Check kubernetes status or kubeconfig."
            exit 1
        fi
        ColorEcho INFO "Ready to install MLAppDeploy on your WSL2."
    else
        GetPrivileged
        MAX_STEP=$(( WITH_DOCKER * 2 + REGISTRY + DATASTORE + 2 ))

        if [ $WITH_DOCKER ]; then
            PrintStep Install Docker
            #UninstallOnSnapWithWarning docker
            if [[ `IsInstalled docker` == '0' ]]; then
                InstallDocker

                # Add user to docker group
                sudo adduser $USER docker
            else
                ColorEcho DEBUG "Already Installed."
            fi

            PrintStep Verify Docker
            if [[ `VerifyDocker` != "0" ]];
            then
                ColorEcho WARN "Failed to operate docker. Retry install after reboot this system."
                exit 1
            else
                ColorEcho DEBUG "Verified."
            fi
            
            if [ $REGISTRY ]; then
                PrintStep Install Registry
                RUNNING_CONTAINER=`sudo docker ps -q -f label=mlappdeploy.type=registry | wc -l`
                PORT_CONFLICTED_CONTAINERS=`sudo docker ps -q -f publish=5000 --format {{.Names}}`
                PORT_CONFLICTED_PROCESSES=`sudo netstat -ap | grep -e :5000[0-9\ .:*]*LISTEN | awk '{print $7}'`
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
            if [ $DATASTORE ]; then
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
        fi

        # Step 1: Install NVIDIA Container Runtine
        PrintStep Install NVIDIA Container Runtime.
        # Check Nvidia Driver status
        if [ `IsInstalled nvidia-smi` == "0" ];
        then
            ColorEcho WARN "Cannot find NVIDIA Graphic Card."
        elif [ `IsInstalled nvidia-container-runtime` == "1" ];
        then
            ColorEcho INFO "Already installed NVIDIA container runtime."
        else
            ColorEcho INFO "Install NVIDIA container runtime."

            InstallNVIDIAContainerRuntime
        
            if [ `IsInstalled nvidia-container-runtime` == "1" ];
            then
                ColorEcho INFO "Completed installation NVIDIA container runtime."
            else
                ColorEcho ERROR "Failed to install NVIDIA container runtime."
                ColorEcho ERROR "Pass this installation..." 
                ColorEcho ERROR "If you want to use GPU on node, install NVIDIA container runtime at this node manually."
            fi
        fi

        # Step 4: Install Kubernetes
        PrintStep "Install Kubernetes."
        if [[ `kubectl get node >> /dev/null 2>&1; echo $?` != "0" ]]; then
            if [[ `IsInstalled k3sup` == '0' ]]; then
                pushd /tmp
                curl -sLS https://get.k3sup.dev | sh
                sudo install k3sup /usr/local/bin/
                popd
            fi
            if [[ `IsInstalled k3s` == '0' ]]; then
                if [[ `IsInstalled nvidia-container-runtime` != '0' ]];
                then
                    GetContainerdNVIDIATemplateFile
                fi
                if [ $MASTER ]; then
                    # Add priviledged for getting token
                    ColorEcho INFO "Set priviledge for getting token by worker."
                    echo "$USER ALL=NOPASSWD: `which cat`" | sudo tee /etc/sudoers.d/$USER-k3s-token >> /dev/null 2>&1
                    # Install k3s server
                    k3sup install --local --local-path ~/.kube/config --k3s-extra-args \
                        '--disable traefik --write-kubeconfig-mode 644'
                elif [ $WORKER ]; then
                    # Add priviledged for getting token
                    ColorEcho INFO "Set priviledge for getting token by worker."
                    echo "$USER ALL=NOPASSWD: ALL" | sudo tee /etc/sudoers.d/$USER-k3s-token >> /dev/null 2>&1
                    cat /dev/zero | ssh-keygen -q -N "" >> /dev/null 2>&1
                    ssh-copy-id -o 'UserKnownHostsFile=/dev/null' -o 'StrictHostKeyChecking=no' -f $USER@127.0.0.1 >> /dev/null 2>&1
                    ssh-copy-id -o 'UserKnownHostsFile=/dev/null' -o 'StrictHostKeyChecking=no' -f $MASTER_USER@$MASTER_IP >> /dev/null 2>&1
                    # Install k3s agent
                    k3sup join --server-ip $MASTER_IP --user $MASTER_USER --ip 127.0.0.1 --user $USER
                    ColorEcho INFO "Finish join worker node with $MASTER_IP."
                else
                    ColorEcho ERROR "Failed to install kubernetes. You need to run with master or worker command."
                fi
            fi
            export KUBECONFIG=$HOME/.kube/config
            kubectl config set-context default
        else
            ColorEcho "Already installed kubernetes."
        fi
    fi
elif [ $BUILD ]; then
    GetPrivileged

    IS_INSTALLED_DOCKER=`IsInstalled docker`
    MAX_STEP=$(( IS_INSTALLED_DOCKER * -1 + 5 ))

    #UninstallOnSnapWithWarning docker
    if [ ! $IS_INSTALLED_DOCKER ]; then
        PrintStep Install Docker
        InstallDocker

        # Add user to docker group
        sudo adduser $USER docker
    fi

    PrintStep Verify Docker
    if [[ `VerifyDocker` != "0" ]];
    then
        ColorEcho WARN "Failed to operate docker. Retry install after reboot this system."
        exit 1
    else
        ColorEcho DEBUG "Verified."
    fi

    IMAGE_NAME=$REGISTRY_ADDR/mlappdeploy/service
    # Step 5: Build Service Package
    PrintStep "Build Service Image."
    if [[ "$BUILD_FROM" == "local" ]]; then
        ColorEcho INFO "Source from Local."
        cat > /tmp/mlad-service.dockerfile << EOF
FROM        python:latest
COPY        python /workspace
WORKDIR     /workspace
RUN         python setup.py install
EXPOSE      8440
ENTRYPOINT  python -m mlad.service
EOF
        DOCKER_BUILDKIT=0 docker build -t $IMAGE_NAME -f /tmp/mlad-service.dockerfile ..
    else
        ColorEcho INFO "Source from Git."
        docker build -t $IMAGE_NAME -<< EOF
FROM        python:latest
RUN         git clone https://github.com/onetop21/MLAppDeploy.git
WORKDIR     /MLAppDeploy/python
RUN         git checkout -b refactoring origin/refactoring
RUN         python setup.py install
EXPOSE      8440
ENTRYPOINT  python -m mlad.service
EOF
    fi
    VERSION=`docker run -it --rm --entrypoint "mlad" $IMAGE_NAME --version | awk '{print $3}' | tr -d '\r'`
    TAGGED_IMAGE=$IMAGE_NAME:$VERSION
    PrintStep "Tag Version to Image [$VERSION]."
    docker tag $IMAGE_NAME $TAGGED_IMAGE
    PrintStep "Push Image to Registry [$REGISTRY_ADDR]."
    docker push $TAGGED_IMAGE
    if [ $? -ne 0 ]; then
        ColorEcho ERROR 'Failed to upload image. Please check your authentication.'
        ColorEcho ERROR "  $ docker login `echo $REGISTRY_ADDR | awk -F '/' '{print $1}'`"
    fi

elif [ $DEPLOY ]; then
    GetPrivileged
    MAX_STEP=3
    
    if [[ `kubectl get node >> /dev/null 2>&1; echo $?` != "0" ]]; then
        ColorEcho ERROR "Need to install MLAppDeploy environment as master first."
        ColorEcho ERROR "  $ $0 master [ARGS...]."
        exit 1
    fi

    PrintStep "Install NVIDIA Device Plguin."
    if [[ `kubectl -n kube-system get ds/nvidia-device-plugin-daemonset >> /dev/null 2>&1; echo $?` == "0" ]]; then
        ColorEcho 'Already installed NVIDIA device plugin.'
    else
        kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.9.0/nvidia-device-plugin.yml
    fi

    PrintStep "Install Ingress Controller (NGINX)."
    if [ $INGRESS ]; then
        if [[ `kubectl get ns ingress-nginx >> /dev/null 2>&1; echo $?` == "0" ]]; then
            SERVICE_TYPE=`kubectl -n ingress-nginx get svc/ingress-nginx-controller -o go-template={{.spec.type}}`
            case "${SERVICE_TYPE,,}" in
            loadbalancer)
                if [ $LOADBALANCER ]; then
                    ColorEcho "Already installed ingress controller."
                    INGRESS=0
                else
                    ColorEcho INFO "Replace ingress controller to NodePort type."
                fi
                ;;
            nodeport)
                if [ $LOADBALANCER ]; then
                    ColorEcho INFO "Replace ingress controller to LoadBalancer type."
                else
                    ColorEcho "Already installed ingress controller."
                    INGRESS=0
                fi
                ;;
            esac
        else
            if [ $LOADBALANCER ]; then
                ColorEcho INFO "Install Ingress Controller with LoadBalancer Service."
            else
                ColorEcho INFO "Install Ingress Controller with NodePort Service."
            fi
        fi
    fi
    if [ $INGRESS ]; then
        if [ $LOADBALANCER ]; then
            # Install by LoadBalance
            kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.44.0/deploy/static/provider/cloud/deploy.yaml
        else
            # Install by NodePort
            kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.44.0/deploy/static/provider/baremetal/deploy.yaml
        fi
        ColorEcho INFO "Wait to activate ingress controller...(up to 2mins)"
        kubectl wait --for=condition=available --timeout=120s -n ingress-nginx deployment.apps/ingress-nginx-controller
    fi

    PrintStep "Deploy MLAppDeploy Service."
    if [[ "$RESET" == "1" ]]; then
        ColorEcho "Remove installed previous service."
        kubectl delete ns mlad >> /dev/null 2>&1
        kubectl delete clusterrole controller-role >> /dev/null 2>&1
        kubectl delete clusterrolebinding controller-role-binding >> /dev/null 2>&1
        kubectl delete secret regcred
    fi

    IMAGE_NAME=$REGISTRY_ADDR/mlappdeploy/service
    VERSION=`docker run -it --rm --entrypoint "mlad" $IMAGE_NAME --version | awk '{print $3}' | tr -d '\r'`
    TAGGED_IMAGE=$IMAGE_NAME:$VERSION
    if [[ `kubectl get ns mlad >> /dev/null 2>&1; echo $?` == "0" ]]; then
        ColorEcho INFO "Rolling Update..."
        
        kubectl -n mlad set image deployment/mlad-service mlad-service=$TAGGED_IMAGE --record
        kubectl -n mlad rollout restart deployment/mlad-service
        kubectl -n mlad rollout status deployment/mlad-service
        if [ $BETA ]; then
            if [ `kubectl get deploy/mlad-service-beta -n mlad >> /dev/null 2>&1; echo $?` ]; then
                if [ -f mlad-service-beta.yaml ]; then
                    mkdir -p .temp
                    cp mlad-service-beta.yaml .temp/
                    cat >> .temp/kustomization.yaml << EOF
resources:
- mlad-service-beta.yaml
images:
- name: ghcr.io/onetop21/mlappdeploy/service
  newName: $IMAGE_NAME
EOF
                    kubectl apply -k .temp
                else
                    ColorEcho WARN "Beta service deployment only supports git clone status."
                fi
            else
                kubectl -n mlad set image deployment/mlad-service-beta mlad-service=$IMAGE_NAME --record
                kubectl -n mlad rollout restart deployment/mlad-service-beta
                kubectl -n mlad rollout status deployment/mlad-service-beta
            fi
        fi
    else
        ColorEcho "Deploy MLAppDeploy service."
        kubectl create secret generic regcred --from-file=.dockerconfigjson=$HOME/.docker/config.json --type=kubernetes.io/dockerconfigjson
        if [ ! $BETA ]; then
            if [ -f mlad-service.yaml ]; then
                mkdir -p .temp
                cp mlad-service.yaml .temp/
                cat >> .temp/kustomization.yaml << EOF
resources:
- mlad-service.yaml
images:
- name: ghcr.io/onetop21/mlappdeploy/service
  newName: $TAGGED_IMAGE
EOF
                 kubectl apply -k .temp
    #            kubectl apply -f mlad-service.yaml
            else
                mkdir -p /tmp/mlad-service
                cat >> /tmp/mlad-service/kustomization.yaml << EOF
resources:
- https://raw.githubusercontent.com/onetop21/MLAppDeploy/refactoring/scripts/mlad-service.yaml
images:
- name: ghcr.io/onetop21/mlappdeploy/service
  newName: $TAGGED_IMAGE
EOF
                 kubectl apply -k /tmp/mlad-service
    #            kubectl apply -f https://raw.githubusercontent.com/onetop21/MLAppDeploy/refactoring/scripts/mlad-service.yaml
            fi
        else
            if [ -f mlad-service-beta.yaml ]; then
                mkdir -p .temp
                cp mlad-service-beta.yaml .temp/
                cat >> .temp/kustomization.yaml << EOF
resources:
- mlad-service-beta.yaml
images:
- name: ghcr.io/onetop21/mlappdeploy/service
  newName: $IMAGE_NAME
EOF
                kubectl apply -k .temp
            else
                ColorEcho WARN "Beta service deployment only supports git clone status."
            fi
        fi

        if [[ "$?" == "0" ]]; then
            ColorEcho INFO "Wait to activate MLAppDeploy service...(up to 2mins)"
            kubectl wait --for=condition=available --timeout=120s -n mlad deploy/mlad-service
            if [[ "$?" != "0" ]]; then
                ColorEcho ERROR "Cannot verify to deploy MLAppDeploy Service."
                exit 1
            fi
            while [[ -z "$TOKEN_LOG" ]]; do
                sleep 1
                TOKEN_LOG=`kubectl logs -n mlad deploy/mlad-service 2>&1 | head -n1`
            done
            ColorEcho INFO $TOKEN_LOG
        else
            ColorEcho ERROR "Failed to deploy MLApploy Service."
        fi
    fi
    if [[ `kubectl -n ingress-nginx get svc/ingress-nginx-controller >> /dev/null 2>&1; echo $?` == "0" ]]; then
        TYPE=`kubectl -n ingress-nginx get svc/ingress-nginx-controller -o jsonpath={.spec.type}`
        NODEPORT=$(kubectl -n ingress-nginx get -o jsonpath="{.spec.ports[0].nodePort}" services ingress-nginx-controller)
        NODES=$(kubectl get nodes -o jsonpath='{ $.items[*].status.addresses[?(@.type=="InternalIP")].address }')
        if [[ "$TYPE" == "LoadBalancer" ]]; then
            LB_ADDRS=`kubectl -n ingress-nginx get svc/ingress-nginx-controller -o jsonpath="{.status.loadBalancer.ingress[*]['hostname','ip']}"`
            for LB_ADDR in $LB_ADDRS; do
                if [[ "$LB_ADDR" == "localhost" ]]; then
                    LB_ADDR=`HostIP`
                fi
                ColorEcho INFO "Service Address : http://$LB_ADDR"
            done
        elif [[ "$TYPE" == "NodePort" ]]; then
            for NODE in $NODES; do 
                if [[ `curl --connect-timeout 1 -s $NODE:$NODEPORT >> /dev/null 2>&1; echo $?` == "0" ]]; then
                    ColorEcho INFO "Service Address : http://$NODE:$NODEPORT"
                fi
            done
        else
            ColorEcho WARN "Not supported ingress service type."
        fi
    else
        ColorEcho ERROR "Failed to get LoadBalancer IP."
    fi
elif [ $UNINSTALL ]; then
    GetPrivileged
    MAX_STEP=1
    PrintStep "Uninstall Kubernetes."
    if [[ `which k3s-uninstall.sh >> /dev/null 2>&1; echo $?` == "0" ]]; then
        ColorEcho INFO "Uninstall master node."
        sudo k3s-uninstall.sh 
    elif [[ `which k3s-agent-uninstall.sh >> /dev/null 2>&1; echo $?` == "0" ]]; then
        ColorEcho INFO "Uninstall worker node."
        sudo k3s-agent-uninstall.sh 
    else
        if [[ `kubectl version >> /dev/null 2>&1; echo $?` == "0" ]]; then
            ColorEcho ERROR "No have permission to remove kubernetes."
        else
            ColorEcho INFO "Already removed kubernetes."
        fi
    fi
fi
