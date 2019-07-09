# Enable GPU on docker swarm
DAEMON_JSON="/etc/docker/daemon.json"
if [ -z `sudo cat $DAEMON_JSON` ]; then
    echo '{}' | sudo tee $DAEMON_JSON
fi
CONFIG=`sudo cat $DAEMON_JSON | jq '."hosts"=["unix:///var/run/docker.sock", "tcp://0.0.0.0"]+."hosts"'`
echo $CONFIG | jq . | sudo tee $DAEMON_JSON

sudo sed -i 's/dockerd\ \-H\ fd\:\/\//dockerd/g' /lib/systemd/system/docker.service

sudo systemctl daemon-reload
sudo systemctl restart docker.service
