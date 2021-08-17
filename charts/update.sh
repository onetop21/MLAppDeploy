#!/bin/bash
WORKDIR=$(dirname $0)
pushd $WORKDIR >> /dev/null 2>&1
for PACKAGE_DIR in $(ls -d */)
do
    pushd $PACKAGE_DIR >> /dev/null 2>&1
    helm dep update && \
    helm dep build
    popd >> /dev/null 2>&1
    helm package $PACKAGE_DIR 
done
helm repo index .
popd >> /dev/null 2>&1
