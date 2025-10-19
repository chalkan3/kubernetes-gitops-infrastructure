#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Building pvc-monitor image..."
podman build -t harbor.kube.chalkan3.com.br/library/pvc-monitor:latest .

echo "Pushing to Harbor..."
podman push --tls-verify=false harbor.kube.chalkan3.com.br/library/pvc-monitor:latest

echo "Done!"
