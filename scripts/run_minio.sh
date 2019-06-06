MINIO_DATA=$HOME/.mlad/master/data
MINIO_CONFIG=$HOME/.mlad/master/minio
mkdir -p $MINIO_DATA $MINIO_CONFIG
docker run -p 9000:9000 --name minio -d -v $MINIO_DATA:/data -v $MINIO_CONFIG:/root/.minio minio/minio server /data
