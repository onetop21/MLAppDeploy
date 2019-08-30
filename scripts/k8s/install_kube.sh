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

######################
# Installing Kubenetes
# Install Runtime
echo "{
  \"exec-opts\": [\"native.cgroupdriver=systemd\"],
  \"log-driver\": \"json-file\",
  \"log-opts\": {
    \"max-size\": \"100m\"
   },
   \"storage-driver\": \"overlay2\"
}" | sudo tee /etc/docker/daemon.json
#cat > /etc/docker/daemon.json <<EOF
#EOF
sudo mkdir -p /etc/systemd/system/docker.service.d

# Install Kubernets
sudo apt-get update && apt-get install -y apt-transport-https curl
curl -s https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -
#cat <<EOF >/etc/apt/sources.list.d/kubernetes.list
#deb https://apt.kubernetes.io/ kubernetes-xenial main
#EOF
echo "
deb https://apt.kubernetes.io/ kubernetes-xenial main
" | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl

# Restart docker
sudo systemctl daemon-reload
sudo systemctl restart docker

# Verify installed docker
docker run --rm hello-world
