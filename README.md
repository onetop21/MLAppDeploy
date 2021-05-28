# MLAppDeploy
Machine Learning Application Deployment Tool by Docker Swarm

[![Docker Image CI](https://github.com/onetop21/MLAppDeploy/actions/workflows/docker-image.yml/badge.svg)](https://github.com/onetop21/MLAppDeploy/actions/workflows/docker-image.yml)
## Environment Installation
### 1. Install MLAppDeploy Environment
``` bash
$ bash scripts/install-mlad-env.sh                  # Install as master node
$ bash scripts/install-mlad-env.sh -b <Master Node> # Install as worker node
$ bash scripts/install-mlad-env.sh -r <Remote Host> # Install at remote host
```
### 2. Deploy Default Services
``` bash
$ bash scripts/deploy-mlad-service.sh                # Deploy services to local master
$ bash scripts/deploy-mlad-service.sh -H <Master IP> # Deploy services to remote master
$ bash scripts/deploy-mlad-service.sh minio          # Deploy minio service only.
```
### 3. Add Insecure Registries (Optional)
```
$ bash scripts/add-insecure-registries.sh <Address with Port>                   # Add insecure registries to all nodes connected with local master
$ bash scripts/add-insecure-registries.sh -H <Remote Host> <Address with Port>  # Add insecure registries to all nodes connected with remote master
```
## Frontend Installation
### 1. Install Virtual Environment
``` bash
$ sudo apt install -y python3-virtualenv
$ python3 -m virtualenv -p python3 <EnvDir>
```
### 2. Enable Virtual Environment
``` bash
$ source <EnvDir>/bin/activate # Enable
(EnvDir) $ deactivate          # Disable (Optional)
```
### 3. Install Python FrontEnd
``` bash
(EnvDir) $ cd frontend
(EnvDir) $ python setup.py install
```

## How to use
### 1. Initialize Configuration
``` bash
(EnvDir) $ mlad config init
Username [<USER>]:
Master IP Address [unix:///var/run/docker.sock]:
```
### 2. Connect External MinIO(S3 Compatible Storage) and Private Docker Registry (Optional)
If you want to connect to your S3 storage and registry, you can attach to external those by modify configurations.
``` bash
(EnvDir) $ mlad config set s3.endpoint=s3.amazonaws.com # Change S3 endpoint
(EnvDir) $ mlad config get                              # Show current configuration
```
### 3. Generate Project File
``` bash
(EnvDir) $ cd <YOUR PROJECT DIR>
(EnvDir) $ mlad project init
Project Name : <Enter Your Project Name>
```
### 4. Customize Project File
Customize project file(**mlad-project.yml**).
### 5. Build Project Image
``` bash
(EnvDir) $ mlad build
```
### 6. Deploy Services on MLAppDeploy
``` bash
(EnvDir) $ mlad up                # Deploy whole services in project.
(EnvDir) $ mlad up <services...>  # Deploy services in project partialy.
```
### 7. Down Service from MLAppDeploy
``` bash
(EnvDir) $ mlad down                # Down whole services in project.
(EnvDir) $ mlad down <services...>  # Down services in project partialy.
```
### 8. Show Logs
``` bash
(EnvDir) $ mlad logs                # Show logs til now.
(EnvDir) $ mlad logs -f             # Show logs with follow.
(EnvDir) $ mlad logs -t             # Show logs with timestamp.
(EnvDir) $ mlad logs <service name> # show logs filtered by service name.
```
### 9. Show Running Service in Project
``` bash
(EnvDir) $ cd <YOUR PROJECT DIR>
(EnvDir) $ mlad ps      # Show running services in project.
(EnvDir) $ mlad ps -a   # Show all services in project
```
### 10. Show All Deployed Project
``` bash
(EnvDir) $ mlad ls
```
### 11. And so on.
You can show more information by below command.
``` bash
(EnvDir) $ mlad --help
```

## Appendix
### Node labeling and constraints
Add label to node.
```bash
(EnvDir) $ mlad node label [ID or HOSTNAME] add [KEY]=[VALUE]
```
Modify constraints at your project file.
```yaml
...
services:
  ...
  service-name:
    ...
    deploy:
      ...
      constraints:
        ...
        labels.[KEY]: [VALUE]
```

#### Example
Labeling.
```bash
(EnvDir) $ mlad node ls
ID          HOSTNAME        ADDRESS       ROLE     STATE  AVAILABILITY  ENGINE    LABELS
abcdef0001  operator-node   192.168.65.1  Manager  Ready  Active        19.03.13
abcdef0002  learner-node    192.168.65.2  Worker   Ready  Active        19.03.13
abcdef0003  actor-node-01   192.168.65.3  Worker   Ready  Active        19.03.13
abcdef0004  actor-node-02   192.168.65.4  Worker   Ready  Active        19.03.13
abcdef0005  actor-node-03   192.168.65.5  Worker   Ready  Active        19.03.13
(EnvDir) $ mlad node label actor-node-01 add type=actor
Added.
(EnvDir) $ mlad node label actor-node-02 add type=actor
Added.
(EnvDir) $ mlad node label actor-node-03 add type=actor
Added.
(EnvDir) $ mlad node ls
ID          HOSTNAME        ADDRESS       ROLE     STATE  AVAILABILITY  ENGINE    LABELS
abcdef0001  operator-node   192.168.65.1  Manager  Ready  Active        19.03.13
abcdef0002  learner-node    192.168.65.2  Worker   Ready  Active        19.03.13
abcdef0003  actor-node-01   192.168.65.3  Worker   Ready  Active        19.03.13  type=actor
abcdef0004  actor-node-02   192.168.65.4  Worker   Ready  Active        19.03.13  type=actor
abcdef0005  actor-node-03   192.168.65.5  Worker   Ready  Active        19.03.13  type=actor
```
Modifying project file.
```yaml
...
services:
  operator:
    ...
    deploy:
      constraints:
        hostname: operator-node
  learner:
    ...
    deploy:
      constraints:
        hostname: learner-node

  actor:
    ...
    deploy:
      constraints:
        replicas: 10
        labels.type: actor
```

