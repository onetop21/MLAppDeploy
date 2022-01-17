#!/bin/bash
WORKDIR=$(dirname $0)
VERSION=$(cd $WORKDIR/../python; python -c "import mlad; print(mlad.__version__)")

# Update values.yaml and Chart.yaml
sed -i "s/^version:.*$/version: $VERSION\t# AUTO GENERATED/" api-server/Chart.yaml
sed -i "s/^appVersion: .*$/appVersion: \"$VERSION\"\t# AUTO GENERATED/" api-server/Chart.yaml
sed -i "s/^  tag: .*$/  tag: $VERSION\t# AUTO GENERATED/" api-server/values.yaml

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
