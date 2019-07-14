# MLAppDeploy
Machine Learning Application Deployment Tool by Docker Swarm
## Installation
### Master
#### 1. Install Docker
``` bash
$ bash scripts/install_docker.sh
```
#### 2. Initialize Docker Swarm
``` bash
$ docker swarm init
```
#### 3. Enable Docker Daemon Remote Mode. (Optional)
```
$ bash scripts/enable_remote_master_docker.sh
```
#### 4. Install Nvidia Docker Runtime if you have GPUs. (Optional)
``` bash
$ bash scripts/install_nvidia_docker_runtime.sh
```
#### 5. Run Default Background Service(MinIO Server, Docker Registry) on Master Server. (Optional)
``` bash
$ bash scripts/run_background_services.sh
```
#### 6. Register Certificate for Docker Registry. (After 3; Optional)
> Connect to MinIO Server (http://IPAddress:9000; Default Access/Secret Key: MLAPPDEPLOY) <br>
> Find certificate (docker-registry/certs/IPADDRESS-PORT/domain.crt) and get shareable link URL <br>
> Run script as below <br>
```
$ bash scripts/register_certs.sh
```
> Paste shareable link.
### Cluster
#### 1. Install Docker
``` bash
$ bash scripts/install_docker.sh
```
#### 2. Check Accessablility to Master.
```
$ bash scripts/check_ACL.sh [Master IP Address]
```
#### 3. Join Docker Swarm
at Master
``` bash
$ docker swarm join-token worker
```
at Cluster
``` bash
$ docker swarm join ...
```
#### 4. Install Nvidia Docker Runtime if you have GPUs. (Optional)
``` bash
$ bash scripts/install_nvidia_docker_runtime.sh
```
#### 5. Register Certificate for Docker Registry. (After Master.3; Optional)
> Connect to MinIO Server (http://IPAddress:9000; Default Access/Secret Key: MLAPPDEPLOY) <br>
> Find certificate (docker-registry/certs/IPADDRESS-PORT/domain.crt) and get shareable link URL <br>
> Run script as below <br>
```
$ bash scripts/register_certs.sh
```
> Paste shareable link.
