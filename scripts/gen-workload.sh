#!/bin/bash
[ $# -ne 2 ] && echo "Usage: $0 <target> <ver>" && exit 1
TARGET=$1
VER=$2
helm template mlappdeploy ../charts/$TARGET/$VER --namespace mlad --create-namespace