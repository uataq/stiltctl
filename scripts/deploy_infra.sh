#!/bin/bash
set -e

if [ "$PROJECT" == "" ]; then
    echo "PROJECT is not set." 1>&2
    exit 1
fi

if [ "$REGION" == "" ]; then
    echo "REGION is not set." 1>&2
    exit 1
fi

cd $(dirname "${BASH_SOURCE[0]}")/../terraform

terraform init -upgrade
terraform apply \
    -var="project=$PROJECT" \
    -var="region=$REGION"

gcloud container clusters get-credentials $PROJECT --region $REGION
