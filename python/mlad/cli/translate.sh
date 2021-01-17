#!/bin/bash
if [[ "$@" =~ .*"--help".* ]]; then
    echo "[How to Use]"
    echo "$ bash $0 [--update] LANGUAGE..."
    echo "[Example]"
    echo "$ bash $0 en_US ko_KR --update"
    exit 1
fi

BASEDIR=`dirname $0`
#find $BASEDIR/locale -name "*.po" | xargs msgfmt -o locale/ko_KR/LC_MESSAGES/mladcli.mo
for po in `ls $BASEDIR/locale/*.po`; do
    LOCALE=`basename ${po/.po/}`
    MESSAGES_DIR=$BASEDIR/locale/$LOCALE/LC_MESSAGES
    mkdir -p $MESSAGES_DIR
    msgfmt -o $MESSAGES_DIR/mladcli.mo $BASEDIR/locale/$LOCALE.po
done
echo Done.
