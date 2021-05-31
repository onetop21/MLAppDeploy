# MLAppDeploy
Machine Learning Application Deployment Tool by Kubernetes

[![Docker Image CI](https://github.com/onetop21/MLAppDeploy/actions/workflows/docker-image.yml/badge.svg)](https://github.com/onetop21/MLAppDeploy/actions/workflows/docker-image.yml)

## Environment Installation
### 1. Install MLAppDeploy Environment
You need docker to use MLAD.
``` bash
$ bash scripts/docker-install.sh
```
Install MLAD environments as master node.
``` bash
$ bash scripts/cluster-install.sh master
```
You can install MLAD environments as worker node with master IP.
``` bash
$ bash scripts/cluster-install.sh worker -i <Master node IP>
```
Build and deploy MLAD service with specified registry.
``` bash
$ bash scripts/cluster-install.sh build --registry <Registry>
$ bash scripts/cluster-install.sh deploy --registry <Registry>
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

## How to use MLAD Project
### 1. Initialize Configuration
``` bash
(EnvDir) $ mlad config init
MLAppDeploy Service Address [http://localhost:8440]:
MLAppDeploy User Token:
Docker Registry Host [docker.io]:
```

#### 1-1. Set User Token
Ask administrator for your user token and login with the token.
``` bash
(EnvDir) $ mlad login
User Token: <user token>
```
If you want to initialize the token, you can logout.
``` bash
(EnvDir) $ mlad logout
```
#### 1-2. Connect External MinIO(S3 Compatible Storage) and Private Docker Registry (Optional)
If you want to connect to your S3 storage and registry, you can attach to external those by modify configurations.
``` bash
(EnvDir) $ mlad config set s3.endpoint=s3.amazonaws.com # Change S3 endpoint
(EnvDir) $ mlad config get                              # Show current configuration
```
### 2. Generate Project File
``` bash
(EnvDir) $ cd <YOUR PROJECT DIR>
(EnvDir) $ mlad project init
Project Name : <Enter Your Project Name>
```
### 3. Customize Project File
Customize project file(**mlad-project.yml**).
### 4. Build Project Image
``` bash
(EnvDir) $ mlad build
```
### 5. Deploy Services on MLAppDeploy
``` bash
(EnvDir) $ mlad up                # Deploy whole services in project.
(EnvDir) $ mlad up <services...>  # Deploy services in project partialy.
```
### 6. Down Service from MLAppDeploy
``` bash
(EnvDir) $ mlad down                # Down whole services in project.
(EnvDir) $ mlad down --no-dump      # Do not save service logs before down.
(EnvDir) $ mlad down <services...>  # Down services in project partialy.
```
### 7. Show Logs
``` bash
(EnvDir) $ mlad logs                # Show logs til now.
(EnvDir) $ mlad logs -f             # Show logs with follow.
(EnvDir) $ mlad logs -t             # Show logs with timestamp.
(EnvDir) $ mlad logs <service name> # show logs filtered by service name.
```
### 8. Show Running Service in Project
``` bash
(EnvDir) $ cd <YOUR PROJECT DIR>
(EnvDir) $ mlad ps      # Show running services in project.
(EnvDir) $ mlad ps -a   # Show all services in project
```
### 9. Show All Deployed Project
``` bash
(EnvDir) $ mlad ls
```
### 10. And so on.
You can show more information by below command.
``` bash
(EnvDir) $ mlad --help
```
## How to use MLAD Plugin
### 1. Initialize Configuration
Same as project. 
### 2. Generate Plugin Project File
``` bash
(EnvDir) $ cd <YOUR Plugin PROJECT DIR>
(EnvDir) $ mlad plugin init
Project Name : <Enter Your Project Name>
```
### 3. Customize Project File
Customize project file(**mlad-plugin.yml**).
### 4. Install Plugin
``` bash
(EnvDir) $ TODO
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
    ports: [6666]
    deploy:
      constraints:
        hostname: operator-node
  learner:
    ...
    ports: [6666]
    deploy:
      constraints:
        hostname: learner-node

  actor:
    ...
    ports: [6666]
    deploy:
      constraints:
        labels.type: actor
      replicas: 10
```

