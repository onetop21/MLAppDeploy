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

##################
# Get master URL #
##################
if [ -z $MASTER_ADDRESS ]; then
    read -p "Advertise URL: " MASTER_ADDRESS
fi
if [ -z $MINIO_PORT ]; then
    read -p "MinIO Port (9000): " MINIO_PORT
    if [ -z $MINIO_PORT ]; then
        MINIO_PORT=9000
    fi
fi
if [ -z $REGISTRY_PORT ]; then
    read -p "Registry Port (5000): " REGISTRY_PORT
    if [ -z $REGISTRY_PORT ]; then
        REGISTRY_PORT=5000
    fi
fi

# Access and secret key
if [ -z $ACCESS_KEY ]; then
    read -p "MinIO Access Key (MLAPPDEPLOY): " ACCESS_KEY
    if [ -z $ACCESS_KEY ]; then
        ACCESS_KEY=MLAPPDEPLOY
    elif [ ${#ACCESS_KEY} -lt 3 ]; then
        echo "Access key length should be between minimum 3 characters in length."
        exit 1
    fi
fi
if [ -z $SECRET_KEY ]; then
    read -p "MinIO Secret Key (MLAPPDEPLOY): " SECRET_KEY
    if [ -z $SECRET_KEY ]; then
        SECRET_KEY=MLAPPDEPLOY
    elif [ ${#SECRET_KEY} -lt 8 ]; then
        echo "Secret key should be in between 8 and 40 characters."
        exit 1
    fi
fi

################
# MinIO Server #
################
MINIO_DATA=$MLAD/master/data
MINIO_CONFIG=$MLAD/master/minio

mkdir -p $MINIO_DATA $MINIO_CONFIG

# Run minio server
docker stop minio > /dev/null 2>&1
docker rm minio > /dev/null 2>&1
docker run -d -p $MINIO_PORT:9000 --restart=always --name minio -e "MINIO_ACCESS_KEY=$ACCESS_KEY" -e "MINIO_SECRET_KEY=$SECRET_KEY" -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data

# Run minio server by service(Swarm)
#echo $ACCESS_KEY | docker secret create access_key -
#echo $SECRET_KEY | docker secret create secret_key -
#docker service create --name="minio" --secret="access_key" --secret="secret_key" -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data


####################
# Docker Registery #
####################
REGISTRY_URL="$MASTER_ADDRESS:$REGISTRY_PORT"
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
    tls:
        certificate: /certs/domain.crt
        key: /certs/domain.key
storage:
    s3:
        accesskey: $ACCESS_KEY
        secretkey: $SECRET_KEY
        region: "us-east-1"
        regionendpoint: "http://$MASTER_ADDRESS:$MINIO_PORT"
        bucket: "docker-registry"
        encrypt: false
        secure: false
        v4auth: true
        chunksize: 5242880
        rootdirectory: /
EOL

# Generate certificates to MinIO
REGISTRY_CERT=$MINIO_DATA/docker-registry/certs/${REGISTRY_URL/:/-}
echo $REGISTRY_CERT

if [ -d $REGISTRY_CERT ]; then
    echo "Already generated certificates."
else
    mkdir -p $REGISTRY_CERT
    
    # Set subjectAltName to openssl.cnf befor generate certificate.
    sudo cp /etc/ssl/openssl.cnf /etc/ssl/openssl.cnf.bak
    sudo sed -i -e "s/\[ v3_ca \]$/\[ v3_ca \]\nsubjectAltName = IP:${REGISTRY_URL/:*/}/" /etc/ssl/openssl.cnf

    # Generate certificate.
    #openssl req -newkey rsa:4096 -nodes -sha256 -keyout $REGISTRY_CERT/domain.key -x509 -days 365 -out $REGISTRY_CERT/domain.crt
    openssl req -newkey rsa:4096 -nodes -sha256 -keyout domain.key -x509 -days 365 -out domain.crt -subj "/C=US/ST=STATE/L=CITY/O=COMPANY/OU=SECTION/CN=$REGISTRY_URL"
    sudo mv domain.key domain.crt $REGISTRY_CERT/

    # Restore openssl configuration.
    sudo mv /etc/ssl/openssl.cnf.bak /etc/ssl/openssl.cnf
fi

# Make default S3 bucket
mkdir -p $MINIO_DATA/logs 
mkdir -p $MINIO_DATA/models 

# Run docker registry server
docker stop registry > /dev/null 2>&1
docker rm registry > /dev/null 2>&1
docker run -d -p 5000:5000 --restart=always -v "$REGISTRY_CERT":/certs -v $REGISTRY_CONFIG:/etc/docker/registry --name registry registry:2

# Run docker registry server by service(Swarm)
# docker secret create domain.crt $REGISTRY_CONFIG/certs/domain.crt
# docker secret create domain.key $REGISTRY_CONFIG/certs/domain.key
# docker node update --label-add registry=true node01
# docker service create --name registry --secret domain.crt --secret domain.key --constraint 'node.labels.registry==true' -p 5000:5000 -e REGISTRY_HTTP_ADDR=0.0.0.0:5000 -e REGISTRY_HTTP_TLS_CERTIFICATE=/etc/docker/registry/certs/domain.crt -e REGISTRY_HTTP_TLS_KEY=/etc/docker/registry/certs/domain.key -v $REGISTRY_CONFIG:/etc/docker/registry registry:2

# Run Tensorboard
docker stop tensorboard > /dev/null 2>&1
docker rm tensorboard > /dev/null 2>&1
docker run -d -p 6006:6006 --restart=always -v "$MINIO_DATA/logs":/logs --name tensorboard tensorflow/tensorflow tensorboard --logdir /logs
