# GitOps com Helmfile e ArgoCD

Este repositório contém a configuração GitOps para deploy de RabbitMQ e Knative usando Helmfile e ArgoCD.

## Estrutura do Repositório

```
.
├── helmfile.yaml                          # Configuração principal do Helmfile
├── values/
│   └── rabbitmq-values.yaml              # Valores customizados para o RabbitMQ
├── argocd/
│   ├── root-app.yaml                     # App of Apps principal (deploy tudo)
│   └── apps/                             # Applications individuais
│       ├── application.yaml              # RabbitMQ
│       ├── knative-serving.yaml          # Knative Serving (CRDs + Core)
│       ├── knative-eventing.yaml         # Knative Eventing (CRDs + Core)
│       ├── kourier.yaml                  # Kourier (Ingress)
│       ├── knative-config.yaml           # Configurações Knative
│       └── applicationset.yaml           # ApplicationSet (alternativa)
├── knative/                              # Manifestos Knative com Kustomize
│   ├── serving-crds/
│   │   └── kustomization.yaml
│   ├── serving-core/
│   │   └── kustomization.yaml
│   ├── eventing-crds/
│   │   └── kustomization.yaml
│   ├── eventing-core/
│   │   └── kustomization.yaml
│   ├── kourier/
│   │   └── kustomization.yaml
│   └── config/
│       ├── kustomization.yaml
│       ├── config-network.yaml
│       └── config-domain.yaml
├── manifests/
│   ├── knative-config.yaml               # Configurações legadas
│   └── install-knative.sh                # Script instalação manual
└── README.md
```

## Pré-requisitos

- Cluster Kubernetes
- ArgoCD instalado
- Plugin Helmfile para ArgoCD
- Acesso ao Gitea
- Nós com label `workload=tools` para deploy do RabbitMQ

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
- **NodeSelector**: `workload=tools` - Deploy apenas em nós com esta label
- **Tolerations**: Configurado para tolerar taints `workload=tools:NoSchedule`

### Preparar Nós para RabbitMQ

Os nós precisam ter a label apropriada:

```bash
# Listar nós
kubectl get nodes

# Adicionar label ao nó
kubectl label nodes <node-name> workload=tools

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

---

## Knative

Este repositório também inclui configuração para deploy do Knative Serving e Eventing.

### Componentes do Knative

- **Knative Serving**: Plataforma serverless para deploy e gerenciamento de cargas de trabalho
- **Knative Eventing**: Sistema de gerenciamento e entrega de eventos
- **Kourier**: Ingress leve para Knative Serving

### Deploy do Knative via ArgoCD

Este repositório usa o padrão "App of Apps" do ArgoCD para gerenciar todo o cluster, incluindo Knative.

#### Deploy Completo (Recomendado)

Para deployar todo o cluster (RabbitMQ + Knative) gerenciado pelo ArgoCD:

```bash
# Aplicar a Application principal que gerencia todas as outras
kubectl apply -f argocd/root-app.yaml
```

Isso criará automaticamente:
- RabbitMQ
- Knative Serving (CRDs + Core)
- Knative Eventing (CRDs + Core)
- Kourier (Ingress)
- Configurações do Knative

#### Deploy Individual

Para deployar apenas componentes específicos:

```bash
# RabbitMQ
kubectl apply -f argocd/apps/application.yaml

# Knative Serving
kubectl apply -f argocd/apps/knative-serving.yaml

# Kourier
kubectl apply -f argocd/apps/kourier.yaml

# Knative Eventing
kubectl apply -f argocd/apps/knative-eventing.yaml

# Configurações do Knative
kubectl apply -f argocd/apps/knative-config.yaml
```

#### Como Funciona

O repositório usa **Kustomize** com **sync waves** do ArgoCD para garantir a ordem correta de instalação:

1. **Wave 1**: CRDs do Knative Serving e Eventing
2. **Wave 2**: Core do Knative Serving e Eventing
3. **Wave 3**: Kourier (Ingress)
4. **Wave 4**: Configurações (ConfigMaps)

Os manifestos são baixados automaticamente dos releases oficiais do Knative via Kustomize.

### Verificar Status do Knative

```bash
# Verificar Knative Serving
kubectl get pods -n knative-serving

# Verificar Kourier
kubectl get pods -n kourier-system

# Verificar Knative Eventing
kubectl get pods -n knative-eventing
```

### Exemplo de Knative Service

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hello
  namespace: default
spec:
  template:
    spec:
      containers:
        - image: gcr.io/knative-samples/helloworld-go
          ports:
            - containerPort: 8080
          env:
            - name: TARGET
              value: "World"
```

Aplicar e testar:

```bash
kubectl apply -f hello-service.yaml

# Obter URL do serviço
kubectl get ksvc hello

# Testar (se tiver DNS configurado)
curl http://hello.default.svc.cluster.local
```

### Configurar Domínio Customizado

Edite o ConfigMap `config-domain` em `manifests/knative-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: config-domain
  namespace: knative-serving
data:
  example.com: ""
```

### Notas Importantes

- Knative requer um cluster Kubernetes 1.28+
- Kourier é usado como ingress leve (alternativa ao Istio)
- As Applications do ArgoCD apontam para os repositórios oficiais do Knative
- Versão do Knative: v1.15.0
