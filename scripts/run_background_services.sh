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
docker stop minio > /dev/null 2>&1
docker rm minio > /dev/null 2>&1
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

# Generate certificates to MinIO
read -p "Private docker registry URL: " REGISTRY_URL
REGISTRY_CERT=$MINIO_DATA/docker-registry/certs/${REGISTRY_URL/:/-}
echo $REGISTRY_CERT

if [ 0 ]; then#[ -d $REGISTRY_CERT ]; then
    echo "Already generated certificates."
else
    mkdir -p $REGISTRY_CERT
    
    # Set subjectAltName to openssl.cnf befor generate certificate.
    sudo cp /etc/ssl/openssl.cnf /etc/ssl/openssl.cnf.bak
    sudo sed -i -e "s/\[ v3_ca \]$/\[ v3_ca \]\nsubjectAltName = IP:${REGISTRY_URL/:*/}/" /etc/ssl/openssl.cnf

    # Generate certificate.
    #openssl req -newkey rsa:4096 -nodes -sha256 -keyout $REGISTRY_CERT/domain.key -x509 -days 365 -out $REGISTRY_CERT/domain.crt
    openssl req -newkey rsa:4096 -nodes -sha256 -keyout $REGISTRY_CERT/domain.key -x509 -days 365 -out $REGISTRY_CERT/domain.crt -subj "/C=US/ST=STATE/L=CITY/O=COMPANY/OU=SECTION/CN=$REGISTRY_URL"

    # Restore openssl configuration.
    sudo mv /etc/ssl/openssl.cnf.bak /etc/ssl/openssl.cnf
fi

# Run docker registry server
docker stop registry > /dev/null 2>&1
docker rm registry > /dev/null 2>&1
docker run -d -p 5000:5000 --restart=always -e REGISTRY_HTTP_ADDR=0.0.0.0:5000 -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/domain.crt -e REGISTRY_HTTP_TLS_KEY=/certs/domain.key -v "$REGISTRY_CERT":/certs -v $REGISTRY_CONFIG:/etc/docker/registry --name registry registry:2

# Run docker registry server by service(Swarm)
# docker secret create domain.crt $REGISTRY_CONFIG/certs/domain.crt
# docker secret create domain.key $REGISTRY_CONFIG/certs/domain.key
# docker node update --label-add registry=true node01
# docker service create --name registry --secret domain.crt --secret domain.key --constraint 'node.labels.registry==true' -p 5000:5000 -e REGISTRY_HTTP_ADDR=0.0.0.0:5000 -e REGISTRY_HTTP_TLS_CERTIFICATE=/etc/docker/registry/certs/domain.crt -e REGISTRY_HTTP_TLS_KEY=/etc/docker/registry/certs/domain.key -v $REGISTRY_CONFIG:/etc/docker/registry registry:2
