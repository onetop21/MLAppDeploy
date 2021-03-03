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
    if [[ `IsInstalled kubectl` == '0' ]]; then
        ColorEcho INFO "Need to install kubernetes on Docker Desktop yourself."
        ColorEcho INFO "Visit and Refer this URL: https://docs.docker.com/docker-for-windows/#kubernetes"
        exit 1
    fi
    kubectl get node 2>&1 >> /dev/null
    if [[ "$?" == "1" ]]; then
        ColorEcho WARN "Check kubernetes status or kubeconfig."
        exit 1
    fi
    ColorEcho INFO "Ready to install MLAppDeploy on your WSL2."
else
    MAX_STEP=7

    GetPrivileged

    # Step 1: Install Requires
    PrintStep "Install Requires Utilities."
    RequiresFromApt jq

    # Step 2: Install Kubernetes
    PrintStep "Install light-weight kubernetes."
    if [[ `IsInstalled k3sup` == '0' ]]; then
        curl -sLS https://get.k3sup.dev | sh
        sudo install k3sup /usr/local/bin/
    fi
    if [[ `IsInstalled k3s` == '0' ]]; then
        k3sup install --local --local-path ~/.kube/config --k3s-extra-args '--docker --no-deploy traefik'
    fi
    export KUBECONFIG=/home/onetop21/.kube/config
    kubectl config set-context default

    # Step 3: Install Docker
    PrintStep "Install docker."
    UninstallOnSnapWithWarning docker
    if [[ `IsInstalled docker` == '0' ]]; then
        InstallDocker

        # Add user to docker group
        sudo adduser $USER docker
    fi

    if [[ `VerifyDocker` != "0" ]];
    then
        ColorEcho INFO "Need to reboot and retry install to continue install docker for MLAppDeploy."
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

# Step 5: Install Load Balancer
PrintStep "Install Load Balancer."
kubectl get service -A | grep LoadBalancer 2>&1 >> /dev/null
if [[ "$?" != "0" ]]; then
    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.44.0/deploy/static/provider/cloud/deploy.yaml
    kubectl wait --for=condition=available --timeout=120s -n ingress-nginx deployment.apps/ingress-nginx-controller
else
    ColorEcho "Already Installed LoadBalancer"
fi

INGRESS_ANNOTATIONS_NGINX='
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "0"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
'
INGRESS_ANNOTATIONS_TRAEFIK='
  annotations:
    kubernetes.io/ingress.class: traefik
    traefik.frontend.rule.type: PathPrefixStrip
'

#read -p "Type Access Key of MinIO (Default: MLAPPDEPLOY) : " ACCESS_KEY
REGISTRY=`HostIP`:5000
PrintStep "Build MLAppDeploy Service."
cat << EOF | docker build -t $REGISTRY/mlad/service -f MLADService-Dockerfile ../..
FROM    python:latest

#RUN     git clone https://github.com/onetop21/MLAppDeploy.git /workspace
#RUN     git checkout -b refactoring origin/refactoring
#WORKDIR /workspace/python

COPY    python /workspace
WORKDIR /workspace
RUN     python setup.py install

EXPOSE  8440

ENTRYPOINT  python -m mlad.service
EOF
docker push $REGISTRY/mlad/service

PrintStep "Deploy MLAppDeploy Service."
ColorEcho "Remove Installed Previous Service."
kubectl delete ns mlad 2>&1 >> /dev/null
cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: mlad
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mlad-service
  namespace: mlad
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mlad-service
  template:
    metadata:
      labels:
        app: mlad-service
    spec:
      containers:
        - name: mlad-service
          image: $REGISTRY/mlad/service:latest
          env:
            - name: MLAD_DEBUG
              value: "1"
            - name: MLAD_KUBE
              value: "1"
            - name: PYTHONUNBUFFERED
              value: "1"
          ports:
          - name: http
            containerPort: 8440
---
kind: Service
apiVersion: v1
metadata:
  name: mlad-service
  namespace: mlad
  labels:
    app: mlad-service
spec:
  selector:
    app: mlad-service
  ports:
  - name: http
    port: 8440
    targetPort: 8440
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mlad-service
  namespace: mlad
$INGRESS_ANNOTATIONS_NGINX
spec:
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: mlad-service
            port:
              number: 8440
---
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: controller-role
rules:
- apiGroups: ["", "apps", "batch", "extensions", "networking.k8s.io"]
  resources: ["nodes", "namespaces", "services", "pods", "pods/log", "deployments", "replicaset", "jobs", "configmaps", "secrets", "events", "ingresses"]
  verbs: ["get", "watch", "list", "create", "update", "delete", "patch", "deletecollection"]
---
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
    name: controller-role-binding
subjects:
- kind: ServiceAccount
  name: default
  namespace: mlad
roleRef:
  kind: ClusterRole
  name: controller-role
  apiGroup: rbac.authorization.k8s.io
---
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: service-role
rules:
- apiGroups: ["", "apps", "batch", "extensions", "networking.k8s.io"]
  resources: ["services", "pods", "pods/log", "deployments", "replicaset", "jobs", "configmaps", "secrets", "events", "ingresses"]
  verbs: ["get", "watch", "list", "create", "update", "delete", "patch", "deletecollection"]
EOF
if [[ "$?" == "0" ]]; then
    kubectl wait --for=condition=available --timeout=120s -n mlad deploy/mlad-service
    while [[ -z "$TOKEN_LOG" ]]; do
        sleep 1
        TOKEN_LOG=`kubectl logs -n mlad deploy/mlad-service 2>&1 | head -n1`
    done
    ColorEcho INFO $TOKEN_LOG
    LB_ADDR=`kubectl get svc -A | grep LoadBalancer | awk '{print $5}'`
    if [[ "$LB_ADDR" == "localhost" ]]; then
        LB_ADDR=`HostIP`
    fi
    ColorEcho INFO "Service Address : http://$LB_ADDR"
else
    ColorEcho WARN "Failed to get admin token."
fi
