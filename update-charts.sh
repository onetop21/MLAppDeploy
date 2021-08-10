#!/bin/bash
pushd charts >> /dev/null 2>&1
for PACKAGE_DIR in $(ls -d */)
do
    for VERSION_DIR in $(ls -d $PACKAGE_DIR*/)
    do
        pushd $VERSION_DIR >> /dev/null 2>&1
        #helm dep update && \
        helm dep build
        popd >> /dev/null 2>&1
        helm package $VERSION_DIR 
    done
done
helm repo index .
popd >> /dev/null 2>&1