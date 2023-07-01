#!/bin/bash

if [[ ! -e './node_modules' ]]; then
    echo "==== running install ===="
    yarn install
fi

if [ $BUILD_ENV == 'prod' ];then
    echo "==== running prod ===="
    yarn build
    yarn start
else
    echo "==== running dev ===="
    yarn dev
fi