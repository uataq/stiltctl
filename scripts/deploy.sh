#!/bin/bash
set -e

if [ "$PROJECT" == "" ]; then
    echo "PROJECT is not set." 1>&2
    exit 1
fi

if [ "$ENVIRONMENT" == "" ]; then
    echo "ENVIRONMENT is not set." 1>&2
    exit 1
fi

ARTIFACT_BUCKET=${ARTIFACT_BUCKET:-$PROJECT-$ENVIRONMENT}

cd $(dirname "${BASH_SOURCE[0]}")/..

IMAGE=gcr.io/$PROJECT/stiltctl

# TODO: this should just reference commit SHA during CICD.
IMAGE_TAG=$(openssl rand -hex 8)
echo "Using image tag: $IMAGE_TAG"

docker build -t stiltctl -t $IMAGE:$IMAGE_TAG .
docker push $IMAGE:$IMAGE_TAG

helm upgrade --install stiltctl ./helm \
    --dependency-update \
    --namespace=$ENVIRONMENT \
    --set image=$IMAGE \
    --set imageTag=$IMAGE_TAG \
    --set environment=$ENVIRONMENT
