#!/bin/bash
if [[ "$@" =~ .*"--help".* ]]; then
    echo "[How to Use]"
    echo "$ bash $0 [--update] LANGUAGE..."
    echo "[Example]"
    echo "$ bash $0 en_US ko_KR --update"
    exit 1
fi

BASEDIR=`dirname $0`
if [[ "$@" =~ .*"--update".* ]]; then
    echo "Generate base POT file."
    find $BASEDIR -name "*.py" | xargs xgettext --language=python --keyword=T -d mladcli -o $BASEDIR/locale/base.pot
    set -- ${@/--update/}
fi
for locale in ${@:-en_US}; do
    echo Generate Translation file... [$locale]
    msginit --input $BASEDIR/locale/base.pot --locale=$LOCALE --output=$BASEDIR/locale/$locale.po
done
echo Done.
