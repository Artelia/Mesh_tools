#!/bin/bash
LOCALES=$1


for LOCALE in ${LOCALES}
do
    echo "Processing: ${LOCALE}.ts"
    # Note we don't use pylupdate with qt .pro file approach as it is flakey
    # about what is made available.
    lrelease telemac_tools/i18n/TelemacTools_${LOCALE}.ts
done
