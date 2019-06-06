# Create master node on docker-machine
docker-machine create -d virtualbox node-master

# Expose ports
VBoxManage controlvm node-master natpf1 "minio,tcp,,9000,,9000"
VBoxManage controlvm node-master natpf1 "registry,tcp,,5000,,5000"
