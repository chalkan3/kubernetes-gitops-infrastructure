# Cert Automation

Automação de certificados TLS para Kubernetes Ingress usando mkcert e Knative Eventing.

## Funcionalidade

Este chart cria uma automação que:
1. Monitora eventos de criação/atualização de Ingress no cluster
2. Quando detecta um novo Ingress, verifica se o hostname está no domínio base configurado
3. Distribui automaticamente o CA do mkcert para todos os nodes do cluster
4. Reinicia o containerd em cada node para aplicar as mudanças

## Pré-requisitos

- Knative Serving instalado
- Knative Eventing instalado
- Certificado mkcert CA gerado
- Chave SSH para acesso aos nodes

## Instalação

```bash
helm install cert-automation ./charts/cert-automation \
  --namespace cert-automation \
  --create-namespace \
  --set-file sshKey=$HOME/.ssh/kubernetes-clusters/production.pem \
  --set-file mkcertCA.cert="$HOME/Library/Application Support/mkcert/rootCA.pem" \
  --set-file mkcertCA.key="$HOME/Library/Application Support/mkcert/rootCA-key.pem"
```

## Configuração

Veja `values.yaml` para todas as opções de configuração disponíveis.
