#!/bin/bash

set -o pipefail
set -o errexit
set -o nounset

# Used to deploy

export SOURCE_DIR=$1
export LOGLEVEL=40
export IMAGE_NAME=arxiv/${SOURCE_DIR}
if [ -z "${TRAVIS_TAG}" ]; then
    export SOURCE_REF=${TRAVIS_COMMIT}
else
    export SOURCE_REF=${TRAVIS_TAG}
fi

helm package --version ${SOURCE_REF} --appVersion ${SOURCE_REF} ./deploy/filemanager/
helm s3 push filemanager-${SOURCE_REF}.tgz arxiv  || echo "This chart version already published"
