#!/bin/bash
LOCALES=$1


for LOCALE in ${LOCALES}
do
    echo "Processing: MeshTools_${LOCALE}.ts"
    # Note we don't use pylupdate with qt .pro file approach as it is flakey
    # about what is made available.
    lrelease mesh_tools/i18n/MeshTools_${LOCALE}.ts
done
