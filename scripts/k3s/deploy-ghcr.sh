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
    ColorEcho INFO "MLAppDeploy Environment Easy Install Script (Kubernetes)"
    ColorEcho WARN "Environments"
    ColorEcho      "    -r, --role=(master, worker)   : Choose environment role."
    ColorEcho      "                                    If not define role, skip environment installation."
    ColorEcho      "        --master-ip=[ADDRESS]     : Join to master node if choosed worker role."
    ColorEcho      "        --master-user=[USERNAME]  : Account name of master node to join if choosed worker role."
    ColorEcho      "                                    (Default: $USER)"
    ColorEcho      "    -u, --uninstall               : Uninstall kubernetes environments."
    ColorEcho      "                                    But, no remove DOCKER and NVIDIA CONTAINER RUNTIME."
    ColorEcho WARN "Deployments"
    ColorEcho      "        --registry=[REPO/ORG]     : Change target to deploy and pulling service image."
    ColorEcho      "                                    (Default: ghcr.io/onetop21)"
    ColorEcho      "        --lb-mode                 : Set ingress service to LoadBalancer."
    ColorEcho      "                                    (Default: NodePort)"
    ColorEcho      "    -b, --with-build              : Build and deploy service image."
    ColorEcho      "        --build-from=(git, local) : Choose source path to build. (Default: git)"
    ColorEcho      "        --config=[PATH]           : Set service configure file. (Not yet)"
    ColorEcho      "        --redeploy                : Re-deploy service image forcely."
    ColorEcho      "    -h, --help                    : This page"
    exit 1
}

# Default variables
REGISTRY=ghcr.io/onetop21 # ref, https://github.com/onetop21/MLAppDeploy
MASTER_USER=$USER
OPTIONS=$(getopt -o r:ubh --long role:,master-ip:,master-user:,uninstall,registry:,lb-mode,with-build,build-from:,config:,redeploy,help -- "$@")
[ $? -eq 0 ] || Usage
eval set -- "$OPTIONS"
while true; do
    case "$1" in
    -r|--role) shift
        ROLE=$1
        ;;
    --master-ip) shift
        MASTER_IP=$1
        ;;
    --master-user) shift
        MASTER_USER=$1
        ;;
    -u|--uninstall)
        UNINSTALL=1
        ;;
    --registry) shift
        REGISTRY=$1
        ;;
    --lb-mode)
        LB_MODE=1
        ;;
    -b|--with-build)
        WITH_BUILD=1
        ;;
    --build-from) shift
        BUILD_FROM=$1
        ;;
    --config) shift
        CONFIG_PATH=$1
        ;;
    --redeploy)
        REDEPLOY=1
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

if [[ "$ROLE" == "worker" ]] && [[ -z "$MASTER_IP" ]]; then
    ColorEcho ERROR "Need an argument \"--master-ip [IP ADDRESS]\", to install environments on worker role node."
    exit 1
fi

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

function VerCompare () {
    if [[ $1 == $2 ]]; then
        echo 0
        return
    fi
    local IFS=.
    local i ver1=(${1/v/}) ver2=(${2/v/})
    # fill empty fields in ver1 with zeros
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++)); do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++)); do
        if [[ -z ${ver2[i]} ]]; then
            # fill empty fields in ver2 with zeros
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]})); then
            echo 1
            return
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]})); then
            echo 2
            return
        fi
    done
    echo 0
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
    if [ "`echo $CONFIG | jq '."default-runtime"'`" != "nvidia" ];
    then
        CONFIG=`echo $CONFIG | jq '."default-runtime"="nvidia"'`
    fi
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
    MAX_STEP=7

    GetPrivileged

    # Step 1: Install Requires
    PrintStep "Install Requires Utilities."
    RequiresFromApt jq

    # Step 2: Install Docker
    PrintStep "Install Docker."
    DAEMON_JSON=/etc/docker/daemon.json
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

    # Step 3: Install NVIDIA Container Runtine
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
        
            if [ `VerifyDocker --gpus all` == "0" ];
            then
                ColorEcho INFO "Completed installation NVIDIA container runtime."
            else
                ColorEcho ERROR "Failed to install NVIDIA container runtime."
                ColorEcho ERROR "Pass this installation..." 
                ColorEcho ERROR "If you want to work GPU normally, install NVIDIA container runtimeat this node manually."
            fi
        fi
    fi

    if [[ "$UNINSTALL" == "1" ]]; then
        PrintStep "Uninstall Kubernetes."
        if [[ `which k3s-uninstall.sh >> /dev/null 2>&1; echo $?` == "0" ]]; then
            sudo k3s-uninstall.sh 
        else
            if [[ `kubectl version >> /dev/null 2>&1; echo $?` == "0" ]]; then
                ColorEcho ERROR "No have permission to remove kubernetes."
            else
                ColorEcho INFO "Already removed kubernetes."
            fi
        fi
        exit 0
    fi

    # Step 4: Install Kubernetes
    PrintStep "Install Kubernetes."
    if [[ -z "$ROLE" ]]; then
        ColorEcho INFO "Skip kubernetes installation."
    else
        if [[ `kubectl get node >> /dev/null 2>&1; echo $?` != "0" ]]; then
            if [[ `IsInstalled k3sup` == '0' ]]; then
                curl -sLS https://get.k3sup.dev | sh
                sudo install k3sup /usr/local/bin/
            fi
            if [[ `IsInstalled k3s` == '0' ]]; then
                if [[ "$ROLE" == "master" ]]; then
                    k3sup install --local --local-path ~/.kube/config --k3s-extra-args '--docker --no-deploy traefik --write-kubeconfig-mode 644'
                elif [[ "$ROLE" == "worker" ]]; then
                    k3sup join --server-ip $MASTER_IP --user $MASTER_USER
                else
                    ColorEcho WARN "Skip kubernetes installation. $ROLE is invalid role."
                fi
            fi
            export KUBECONFIG=$HOME/.kube/config
            kubectl config set-context default
        else
            ColorEcho "Already installed kubernetes."
        fi
    fi
fi

# Check Pre-requires
if [[ `IsInstalled docker` == '0' ]]; then
    ColorEcho ERROR "Pre-required docker installation."
    exit 1
fi
IMAGE_NAME=$REGISTRY/mlappdeploy/service
if [[ "$WITH_BUILD" == "1" ]]; then
    # Step 5: Build Service Package
    PrintStep "Build Service Image."
    if [[ "$BUILD_FROM" == "local" ]]; then
        ColorEcho INFO "Source from Local."
        cat >> /tmp/mlad-service.dockerfile << EOF
FROM        python:latest
COPY        python /workspace
WORKDIR     /workspace
RUN         python setup.py install
EXPOSE      8440
ENTRYPOINT  python -m mlad.service
EOF
        DOCKER_BUILDKIT=0 docker build -t $IMAGE_NAME -f /tmp/mlad-service.dockerfile ../..
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
    docker tag $IMAGE_NAME $TAGGED_IMAGE
    docker push $IMAGE_NAME
    kubectl create secret generic regcred --from-file=.dockerconfigjson=$HOME/.docker/config.json --type=kubernetes.io/dockerconfigjson
fi

# Check pre-requires
if [[ `kubectl get node >> /dev/null 2>&1; echo $?` == "1" ]]; then
    ColorEcho ERROR "Pre-required kubernetes installation."
    exit 1
fi
# Step 6: Install NVIDIA Device Plugin
PrintStep "Install NVIDIA Device Plguin."
if [[ `kubectl -n kube-system get ds/nvidia-device-plugin-daemonset >> /dev/null 2>&1; echo $?` == "0" ]]; then
    ColorEcho 'Already installed NVIDIA device plugin.'
else
    kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v0.9.0/nvidia-device-plugin.yml
fi

# Step 5: Install Load Balancer
#read -p "Type Access Key of MinIO (Default: MLAPPDEPLOY) : " ACCESS_KEY
PrintStep "Install Load Balancer."
KUBE_VERSION=`kubectl version -o json | jq .serverVersion.gitVersion | tr -d \"`
if [[ `kubectl get ns ingress-nginx >> /dev/null 2>&1; echo $?` == "0" ]]; then
    ColorEcho "Already installed ingress."
else
    #if [[ `VerCompare $KUBE_VERSION v1.19` == '1' ]]; then
    if [[ "$LB_MODE" == "1" ]]; then
        ColorEcho INFO "Install Ingress Using LoadBalancer."
        # Install by LoadBalance
        kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.44.0/deploy/static/provider/cloud/deploy.yaml
    else
        # Install by NodePort
        ColorEcho INFO "Install Ingress Using NodePort."
        kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v0.44.0/deploy/static/provider/baremetal/deploy.yaml
    fi
    kubectl wait --for=condition=available --timeout=120s -n ingress-nginx deployment.apps/ingress-nginx-controller
fi

PrintStep "Deploy MLAppDeploy Service."
if [[ "$REDEPLOY" == "1" ]]; then
    ColorEcho "Remove installed previous service."
    kubectl delete ns mlad >> /dev/null 2>&1
fi
if [[ `kubectl get ns mlad >> /dev/null 2>&1; echo $?` == "0" ]]; then
    ColorEcho INFO "Rolling Update..."
    kubectl -n mlad set image deployment/mlad-service mlad-service=$IMAGE_NAME --record
    kubectl -n mlad rollout status deployment/mlad-service
else
    ColorEcho "Deploy MLAppDeploy service."
    kubectl delete clusterrole controller-role
    kubectl delete clusterrolebinding controller-role-binding
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
      terminationGracePeriodSeconds: 0
      containers:
        - name: mlad-service
          image: $IMAGE_NAME
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
      imagePullSecrets:
        - name: regcred
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
apiVersion: networking.k8s.io/v1beta1
kind: Ingress
metadata:
  name: mlad-service
  namespace: mlad
  annotations:
    kubernetes.io/ingress.class: nginx
    nginx.ingress.kubernetes.io/proxy-body-size: "0"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
    #kubernetes.io/ingress.class: traefik
    #traefik.frontend.rule.type: PathPrefixStrip
spec:
  rules:
  - http:
      paths:
      - path: /
        #pathType: Prefix
        backend:
          serviceName: mlad-service
          servicePort: 8440
---
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: controller-role
rules:
- apiGroups: ["", "apps", "batch", "extensions", "rbac.authorization.k8s.io", "networking.k8s.io"]
  resources: ["nodes", "namespaces", "services", "pods", "pods/log", "replicationcontrollers", "deployments", "replicaset", "jobs", "configmaps", "secrets", "events", "rolebindings", "ingresses"]
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
EOF
    if [[ "$?" == "0" ]]; then
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

