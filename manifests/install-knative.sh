#!/bin/bash

# Script para instalar Knative Serving e Eventing
# Execute este script para instalar o Knative no cluster

KNATIVE_VERSION="1.15.0"

echo "Instalando Knative Serving v${KNATIVE_VERSION}..."

# Instalar CRDs do Knative Serving
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v${KNATIVE_VERSION}/serving-crds.yaml

# Instalar Core do Knative Serving
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v${KNATIVE_VERSION}/serving-core.yaml

# Aguardar pods do knative-serving
echo "Aguardando pods do knative-serving ficarem prontos..."
kubectl wait --for=condition=Ready pods --all -n knative-serving --timeout=300s

# Instalar Kourier (Ingress)
echo "Instalando Kourier..."
kubectl apply -f https://github.com/knative/net-kourier/releases/download/knative-v${KNATIVE_VERSION}/kourier.yaml

# Configurar Knative para usar Kourier
kubectl patch configmap/config-network \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'

# Aguardar pods do kourier-system
echo "Aguardando pods do kourier-system ficarem prontos..."
kubectl wait --for=condition=Ready pods --all -n kourier-system --timeout=300s

# Instalar Knative Eventing (opcional)
echo "Instalando Knative Eventing v${KNATIVE_VERSION}..."
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v${KNATIVE_VERSION}/eventing-crds.yaml
kubectl apply -f https://github.com/knative/eventing/releases/download/knative-v${KNATIVE_VERSION}/eventing-core.yaml

# Aguardar pods do knative-eventing
echo "Aguardando pods do knative-eventing ficarem prontos..."
kubectl wait --for=condition=Ready pods --all -n knative-eventing --timeout=300s

echo "Instalação do Knative concluída!"
echo ""
echo "Verificar status:"
echo "  kubectl get pods -n knative-serving"
echo "  kubectl get pods -n kourier-system"
echo "  kubectl get pods -n knative-eventing"
