#!/bin/bash
set -e

# Configurações
IMAGE_NAME="harbor.kube.chalkan3.com.br/library/cert-automation"
IMAGE_TAG="latest"
FULL_IMAGE="${IMAGE_NAME}:${IMAGE_TAG}"

echo "🔨 Building image: $FULL_IMAGE"

# Build com podman
podman build -t "$FULL_IMAGE" .

echo "✅ Build concluído!"
echo ""
echo "📤 Pushing para Harbor..."

# Push para Harbor
podman push --tls-verify=false "$FULL_IMAGE"

echo "✅ Push concluído!"
echo ""
echo "Imagem disponível: $FULL_IMAGE"
