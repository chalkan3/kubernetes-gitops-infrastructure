#!/bin/bash
set -e

IMAGE_NAME="harbor.kube.chalkan3.com.br/library/health-check"
IMAGE_TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo "🔨 Building image: $FULL_IMAGE"
podman build -t "$FULL_IMAGE" .

echo "✅ Build concluído!"
echo "📤 Pushing para Harbor..."
podman push --tls-verify=false "$FULL_IMAGE"

echo "✅ Push concluído!"
echo "Imagem disponível: $FULL_IMAGE"
