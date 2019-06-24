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

# Test nvidia-smi with the latest official CUDA image
docker run --runtime=nvidia --rm nvidia/cuda:9.0-base nvidia-smi

# Enable GPU on docker swarm
DAEMON_JSON="/etc/docker/daemon.json"
if [ -z `sudo cat $DAEMON_JSON` ]; then
    echo '{}' | sudo tee $DAEMON_JSON
fi
GPU_IDS=`nvidia-smi -a | grep UUID | awk '{print substr($4,0,12)}'`
CONFIG=`sudo cat $DAEMON_JSON | jq '."default-runtime"="nvidia"' | jq '."node-generic-resources"=[]'`
for ID in $GPU_IDS; do
    CONFIG=`echo $CONFIG | jq '."node-generic-resources"=["gpu='$ID'"]+."node-generic-resources"'`
done
echo $CONFIG | jq . | sudo tee $DAEMON_JSON
