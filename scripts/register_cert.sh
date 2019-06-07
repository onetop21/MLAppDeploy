if [ -z $1 ]; then
    echo "Run script with argument that shareable link of docker registry certificates file [domain.crt] from MinIO."
    echo "$ $0 [URL]"
    exit 1
else
    URL=$1
fi

if [ ! -z $URL ]; then
    URL_NOARGS="${URL%%\?*}"
    DOMAIN=`echo $URL_NOARGS | awk -F/ '{print $6}'`
    sudo mkdir -p "/etc/docker/certs.d/${DOMAIN/-/:}"
    sudo curl -o "/etc/docker/certs.d/${DOMAIN/-/:}/ca.crt" $URL
    echo "Registered."
else
    echo "No URL."
    exit 1
fi

