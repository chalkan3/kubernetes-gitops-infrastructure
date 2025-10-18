#!/bin/bash
set -e

echo "=== Installing cert-automation with secrets ==="

# Verificar se os arquivos existem
SSH_KEY="$HOME/.ssh/kubernetes-clusters/production.pem"
MKCERT_CERT="$HOME/Library/Application Support/mkcert/rootCA.pem"
MKCERT_KEY="$HOME/Library/Application Support/mkcert/rootCA-key.pem"

if [ ! -f "$SSH_KEY" ]; then
  echo "Error: SSH key not found at $SSH_KEY"
  exit 1
fi

if [ ! -f "$MKCERT_CERT" ]; then
  echo "Error: mkcert CA cert not found at $MKCERT_CERT"
  exit 1
fi

if [ ! -f "$MKCERT_KEY" ]; then
  echo "Error: mkcert CA key not found at $MKCERT_KEY"
  exit 1
fi

# Aplicar a Application no ArgoCD
echo "Applying ArgoCD Application..."
kubectl apply -f argocd/apps/cert-automation.yaml

# Aguardar namespace ser criado
echo "Waiting for namespace..."
sleep 5

# Criar secrets manualmente com os valores reais
echo "Creating secrets with actual values..."

kubectl create secret generic ssh-key \
  --from-file=id_rsa="$SSH_KEY" \
  -n cert-automation \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret generic mkcert-ca \
  --from-file=rootCA.pem="$MKCERT_CERT" \
  --from-file=rootCA-key.pem="$MKCERT_KEY" \
  -n cert-automation \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✅ cert-automation installed successfully!"
echo ""
echo "To check status:"
echo "  kubectl get all -n cert-automation"
echo "  kubectl logs -n cert-automation -l serving.knative.dev/service=cert-manager"
