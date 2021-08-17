# MLAppDeploy API Server

Machine Learning Application Deployment Tool by Kubernetes

## Requires
### Ingress-NGINX (Required)
To access MLAppDeploy API-Server, requires install ingress-nginx on a system.<br>
Run below commands.

`helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx`<br>
`helm repo update`<br>
`helm install ingress-nginx ingress-nginx/ingress-nginx --create-namespace -n ingress-nginx`

### Prometheus Stack (Optional)
To monitoring MLAppDeploy cluster, requires install prometheus stack on a system.<br>
Run below commands.

`helm repo add prometheus-community https://prometheus-community.github.io/helm-charts`<br>
`helm repo update`<br>
```bash
helm install prometheus-stack prometheus-community/kube-prometheus-stack --create-namespace -n monitoring \
    --set grafana.ingress.enabled=true \
    --set grafana.ingress.path=/grafana \
    --set grafana.'grafana\.ini'.server.root_url='%(protocol)s://%(domain)s:%(http_port)s/grafana' \
    --set grafana.'grafana\.ini'.server.serve_from_sub_path=true \
    --set prometheus.ingress.enabled=true \
    --set prometheus.ingress.paths={/prometheus} \
    --set prometheus.ingress.pathType=Prefix \
    --set prometheus.prometheusSpec.routePrefix=/prometheus \
    --set prometheus.prometheusSpec.externalUrl=/prometheus \
    --set alertmanager.ingress.enabled=true \
    --set alertmanager.ingress.annotations.'nginx\.ingress\.kubernetes\.io/rewrite-target'='/$2' \
    --set alertmanager.ingress.paths='{/alertmanager(/|$)(.*)}'
```

#### GPU Metrics Dashboard
We provide an official dashboard on Grafana: https://grafana.com/grafana/dashboards/12239

## Installation

`helm repo add mlappdeploy https://onetop21.github.io/MLAppDeploy/charts`<br>
`helm repo update`<br>
```bash
helm install mlappdeploy mlappdeploy/api-server --create-namespace -n mlad \
    --set serviceMonitor.namespace=monitoring
```
