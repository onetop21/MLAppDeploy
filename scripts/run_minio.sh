MINIO_DATA=$HOME/.mlad/master/data
MINIO_CONFIG=$HOME/.mlad/master/minio

if [ -d /hosthome ]; then
    # In docker-machine
    if [ -z $1 ]; then
        echo 'HOST USERNAME :' $1
    else
        echo 'Run script with username of host.'
        echo "$$ bash $0 [USERNAME]"
        exit 1
    fi

    if [ -d /hosthome/$1 ]; then
        ln -s /hosthome/$1/.mlad $HOME/.mlad
    else
        echo "Cannot find username $1 in host."
        exit 1
    fi
fi

mkdir -p $MINIO_DATA $MINIO_CONFIG
docker run -p 9000:9000 --name minio -d -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data
