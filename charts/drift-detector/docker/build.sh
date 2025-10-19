#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Building drift-detector image..."
podman build -t harbor.kube.chalkan3.com.br/library/drift-detector:latest .

echo "Pushing to Harbor..."
podman push --tls-verify=false harbor.kube.chalkan3.com.br/library/drift-detector:latest

echo "Done!"
