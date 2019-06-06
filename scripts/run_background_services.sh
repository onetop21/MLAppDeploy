# Check in docker-machine

MLAD=$HOME/.mlad

if [ -d /hosthome ]; then
    # In docker-machine
    if [ -z $1 ]; then
        echo 'Run script with username of host.'
        echo "$ bash $0 [USERNAME]"
        exit 1
    else
        echo 'HOST USERNAME :' $1
    fi

    if [ -d /hosthome/$1 ]; then
        ln -s /hosthome/$1/.mlad $MLAD
    else
        echo "Cannot find username $1 in host."
        exit 1
    fi
fi


################
# MinIO Server #
################

MINIO_DATA=$MLAD/master/data
MINIO_CONFIG=$MLAD/master/minio

mkdir -p $MINIO_DATA $MINIO_CONFIG

# Access and secret key
if [ -z $ACCESS_KEY ]; then
    ACCESS_KEY=MLAPPDEPLOY
fi
if [ -z $SECRET_KEY ]; then
    SECRET_KEY=MLAPPDEPLOY
fi

# Run minio server
docker run -d -p 9000:9000 --restart=always --name minio -e "MINIO_ACCESS_KEY=$ACCESS_KEY" -e "MINIO_SECRET_KEY=$SECRET_KEY" -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data

# Run minio server by service(Swarm)
#echo $ACCESS_KEY | docker secret create access_key -
#echo $SECRET_KEY | docker secret create secret_key -
#docker service create --name="minio" --secret="access_key" --secret="secret_key" -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data


####################
# Docker Registery #
####################

REGISTRY_CONFIG=$MLAD/master/registry

mkdir -p $REGISTRY_CONFIG

# config.yml
cat > $REGISTRY_CONFIG/config.yml << EOL
version: 0.1
log:
    fields:
        service: registry
http:
    addr: :5000
storage:
    cache:
        layerinfo: inmemory
    s3:
        accesskey: $ACCESS_KEY
        secretkey: $SECRET_KEY
        region: "us-east-1"
        regionendpoint: "http://localhost:9000"
        bucket: "docker-registry"
        encrypt: false
        secure: true
        v4auth: true
        chunksize: 5242880
        rootdirectory: /
EOL
docker run -d -p 5000:5000 --restart=always -v $REGISTRY_CONFIG:/etc/docker/registry --name registry registry:2
