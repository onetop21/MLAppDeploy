#!/bin/bash

echo "Install k3sup"
curl -sLS https://get.k3sup.dev | sh
sudo install k3sup /usr/local/bin/

echo "Install k3s"
k3sup install --local --local-path ~/.kube/config --k3s-extra-args '--no-deploy traefik'

echo "Wait to Install k3s"
export KUBECONFIG=/home/onetop21/.kube/config
kubectl config set-context default
kubectl get node -o wide

echo "Install Ambassador"
kubectl apply -f https://www.getambassador.io/yaml/ambassador/ambassador-crds.yaml
kubectl apply -f https://www.getambassador.io/yaml/ambassador/ambassador-rbac.yaml
kubectl apply -f https://www.getambassador.io/yaml/ambassador/ambassador-service.yaml

echo "Install Ingress Service"
cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: mlad
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: registry
  namespace: mlad
spec:
  replicas: 1
  selector:
    matchLabels:
      app: registry
  template:
    metadata:
      labels:
        app: registry
    spec:
      containers:
        - name: registry
          image: registry:2.6.2
          env:
            - name: REGISTRY_HTTP_ADDR
              value: ":5000"
            - name: REGISTRY_STORAGE_FILESYSTEM_ROOTDIRECTORY
              value: "/var/lib/registry"
          ports:
          - name: http
            containerPort: 5000
          volumeMounts:
          - name: image-store
            mountPath: "/var/lib/registry"
      volumes:
        - name: image-store
          emptyDir: {}

---
kind: Service
apiVersion: v1
metadata:
  name: registry
  namespace: mlad
  labels:
    app: registry
spec:
  selector:
    app: registry
  ports:
  - name: http
    port: 5000
    targetPort: 5000
---
apiVersion: getambassador.io/v2
kind: Mapping
metadata:
  name: mlad-service
  namespace: mlad
spec:
  prefix: /registry/
  service: http://registry.mlad:5000
EOF
