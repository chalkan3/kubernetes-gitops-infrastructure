#!/bin/bash
set -e

IMAGE_NAME="harbor.kube.chalkan3.com.br/library/scaler-advisor"
IMAGE_TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo "🔨 Building: $FULL_IMAGE"
podman build -t "$FULL_IMAGE" .
echo "📤 Pushing..."
podman push --tls-verify=false "$FULL_IMAGE"
echo "✅ Done: $FULL_IMAGE"
