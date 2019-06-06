# Uninstall old version
sudo apt-get remove docker docker-engine docker.io containerd runc

# Update package manager
sudo apt-get update

# Install package to use repository over HTTPS
sudo apt-get install \
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
sudo apt-get install docker-ce docker-ce-cli containerd.io

# Add user to docker group
sudo adduser $USER docker
sudo systemctl daemon-reload
sudo systemctl restart docker

# Verify installed docker
docker run --rm hello-world
