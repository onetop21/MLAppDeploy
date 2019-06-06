MINIO_DATA=$HOME/.mlad/master/data
MINIO_CONFIG=$HOME/.mlad/master/minio

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
        ln -s /hosthome/$1/.mlad $HOME/.mlad
    else
        echo "Cannot find username $1 in host."
        exit 1
    fi
fi

mkdir -p $MINIO_DATA $MINIO_CONFIG

# Access and secret key
if [ -z $ACCESS_KEY ]; then
    ACCESS_KEY=MLAPPDEPLOY
fi
if [ -z $SECRET_KEY ]; then
    SECRET_KEY=MLAPPDEPLOY
fi

# Run minio server
docker run -p 9000:9000 --name minio -d -e "MINIO_ACCESS_KEY=$ACCESS_KEY" -e "MINIO_SECRET_KEY=$SECRET_KEY" -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data

# Run minio server by service(Swarm)
#echo $ACCESS_KEY | docker secret create access_key -
#echo $SECRET_KEY | docker secret create secret_key -
#docker service create --name="minio" --secret="access_key" --secret="secret_key" -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data


# config.yml
"version: 0.1
log:
    fields:
        service: registry
http:
    addr: :5000
storage:
    cache:
        layerinfo: inmemory
    s3:
        accesskey: {MINIO_ACCESS_KEY}
        secretkey: {MINIO_SECRET_KEY}
        region: {REGION}
        regionendpoint: {REGION_ENDPOINT}
        bucket: {BUCKET_NAME}
        encrypt: false
        secure: true
        v4auth: true
        chunksize: 5242880
        rootdirectory: /"
docker run -d -p 5000:5000 --restart=always -v /mnt/registry:/var/lib/registry --name registry registry:2
