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
terraform destroy \
    -var="project=$PROJECT" \
    -var="region=$REGION"

kubectl config delete-cluster gke_${PROJECT}_${REGION}_${PROJECT}
kubectl config delete-context gke_${PROJECT}_${REGION}_${PROJECT}
kubectl config unset users.gke_${PROJECT}_${REGION}_${PROJECT}
