sudo swapoff -a

# Kube init
sudo kubeadm init --pod-network-cidr=10.244.0.0/16 --ignore-preflight-errors=... 

# Configure kuberenetes setting file.
mkdir -p $HOME/.kube
sudo cp -fi /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Install Flannel on kubernetes
kubectl apply -f https://raw.githubusercontent.com/coreos/flannel/master/Documentation/kube-flannel.yml 

# Remove unused flannel without amd64
kubectl delete ds/kube-flannel-ds-ppc64le -n kube-system
kubectl delete ds/kube-flannel-ds-arm64 -n kube-system
kubectl delete ds/kube-flannel-ds-arm -n kube-system
kubectl delete ds/kube-flannel-ds-s390x -n kube-system
