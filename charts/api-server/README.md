# MLAppDeploy API Server

Machine Learning Application Deployment Tool by Kubernetes

## Requires
### Ingress-NGINX (Required)
To access MLAppDeploy API-Server, requires install ingress-nginx on a system.<br>
Run below commands.

`helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx`
`helm repo update`
`helm install ingress-nginx ingress-nginx/ingress-nginx --create-namespace -n ingress-nginx`

### Prometheus Stack (Optional)
To monitoring MLAppDeploy cluster, requires install prometheus stack on a system.<br>
Run below commands.

`helm repo add prometheus-community https://prometheus-community.github.io/helm-charts`
`helm repo update`
```bash
helm install prometheus-stack prometheus-community/kube-prometheus-stack --create-namespace -n monitoring \
    --set prometheus.ingress.enabled=true \
    --set prometheus.ingress.path=/prometheus \
    --set grafana.ingress.enabled=true \
    --set grafana.ingress.path=/grafana
```

## Installation

`helm repo add mlappdeploy https://onetop21.github.io/MLAppDeploy/charts`
`helm repo update`
`helm install mlappdeploy mlappdeploy/api-server --create-namespace -n mlad`