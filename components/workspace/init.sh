#!/bin/bash

# S3 Credentials
mkdir -p /root/.aws
echo "[default]" > /root/.aws/config
cat << EOF >> /root/.aws/credentials
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
EOF

# README.md (SSH)
for _ in {1..10}
do
    PORT=$(curl -s --unix-socket /var/run/docker.sock http://localhost/containers/$HOSTNAME/json | jq '.NetworkSettings.Ports."22/tcp"[0].HostPort // empty' -r)
    echo $PORT
    [ ! -z $PORT ] && break
    sleep 1
done
cat << EOF >> /root/README.md
# How to connect using SSH (default password: password)
$ ssh root@$HOST_IP -p $PORT

# How to access S3 filesystem.
$ s3 mb [bucket name]
$ s3 cp file s3://[bucket]/[path]
$ s3 cp dir s3://[bucket]/[dir]/ --recursive
$ s3 ls s3://[bucket]/[path]...
$ s3 cp s3://[bucket]/[path]/filename [local path]
$ s3 sync s3://[bucket]/[path] [locah path]
$ s3 rm s3://[bucket]/[path] [--recursive]

# How to access by VSCode
## ref. https://code.visualstudio.com/docs/remote/ssh
EOF

# alias
sed -i '/alias s3/d' /root/.bash_aliases
echo "alias s3='aws --endpoint-url $S3_ENDPOINT s3'" >> /root/.bash_aliases

# path
echo "PATH=\$PATH:$PATH" >> /root/.profile

# SSHD and jupyter
/usr/sbin/sshd -D & jupyter lab --allow-root --NotebookApp.token=''
