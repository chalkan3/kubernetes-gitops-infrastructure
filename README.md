# RabbitMQ GitOps com Helmfile e ArgoCD

Este repositório contém a configuração GitOps para deploy do RabbitMQ usando Helmfile e ArgoCD.

## Estrutura do Repositório

```
.
├── helmfile.yaml                 # Configuração principal do Helmfile
├── values/
│   └── rabbitmq-values.yaml     # Valores customizados para o RabbitMQ
├── argocd/
│   └── application.yaml         # Manifesto do ArgoCD Application
└── README.md
```

## Pré-requisitos

- Cluster Kubernetes
- ArgoCD instalado
- Plugin Helmfile para ArgoCD
- Acesso ao Gitea
- Nós com label `node-role=tools` para deploy do RabbitMQ

## Deploy Manual com Helmfile

```bash
# Sincronizar todas as releases
helmfile sync

# Verificar o que será aplicado
helmfile diff

# Aplicar apenas o RabbitMQ
helmfile -l name=rabbitmq sync
```

## Deploy via ArgoCD

1. Aplicar o manifesto do Application:
```bash
kubectl apply -f argocd/application.yaml
```

2. Verificar o status:
```bash
kubectl get applications -n argocd
```

## Configuração do RabbitMQ

O RabbitMQ está configurado com:
- 1 réplica
- Persistência habilitada (8Gi)
- Métricas habilitadas
- Usuário: admin
- Senha: rabbitmq-password (⚠️ alterar em produção)
- Portas:
  - AMQP: 5672
  - Management UI: 15672
- **NodeSelector**: `node-role=tools` - Deploy apenas em nós com esta label
- **Tolerations**: Configurado para tolerar taints `workload=tools:NoSchedule`

### Preparar Nós para RabbitMQ

Os nós precisam ter a label apropriada:

```bash
# Listar nós
kubectl get nodes

# Adicionar label ao nó
kubectl label nodes <node-name> node-role=tools

# Verificar labels
kubectl get nodes --show-labels | grep tools
```

Opcionalmente, adicionar taint para dedicar o nó apenas para workloads tools:

```bash
kubectl taint nodes <node-name> workload=tools:NoSchedule
```

## Acessar o RabbitMQ

### Port-forward para Management UI
```bash
kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672
```

Acesse: http://localhost:15672
- Usuário: admin
- Senha: rabbitmq-password

### Port-forward para AMQP
```bash
kubectl port-forward -n rabbitmq svc/rabbitmq 5672:5672
```

## Customização

Para customizar a instalação, edite o arquivo `values/rabbitmq-values.yaml` e faça commit.
O ArgoCD detectará as mudanças e aplicará automaticamente (se auto-sync estiver habilitado).

## Segurança

⚠️ **IMPORTANTE**: As credenciais padrão devem ser alteradas para produção.

Considere usar:
- Sealed Secrets
- External Secrets Operator
- Vault

## Monitoramento

O RabbitMQ está configurado com métricas habilitadas. Para configurar ServiceMonitor do Prometheus:

```yaml
metrics:
  enabled: true
  serviceMonitor:
    enabled: true
```
