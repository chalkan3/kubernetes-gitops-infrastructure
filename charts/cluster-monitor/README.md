# Cluster Monitor - Monitoramento Automático com Knative e ntfy

Sistema de monitoramento automático do cluster Kubernetes que envia notificações via ntfy.

## 🎯 Funcionalidades

### Monitoramento de Pods
- ✅ CrashLoopBackOff / ImagePullBackOff
- ✅ Pods terminados com erro
- ✅ Pods iniciados (em namespaces de produção)

### Monitoramento de Nodes
- ✅ Node não está pronto (NotReady)
- ✅ Pressão de memória (MemoryPressure)
- ✅ Pressão de disco (DiskPressure)

### Monitoramento de Deployments
- ✅ Réplicas insuficientes (degraded)
- ✅ Recovery (todas as réplicas disponíveis)

### Monitoramento de PVCs
- ✅ PVC pendente (aguardando bind)
- ✅ PVC bound com sucesso

## 📱 Notificações ntfy

O sistema envia notificações com diferentes níveis de prioridade e emojis:

- 🔴 **max/high**: Problemas críticos (node down, crashloop)
- ⚠️ **default**: Avisos importantes
- ✅ **low**: Informações de sucesso

### Exemplo de Notificações

```
🔴 Pod Problem - kube.chalkan3.com.br
Pod: production/api-server
Container: app
Status: CrashLoopBackOff
```

```
✅ Deployment Healthy - kube.chalkan3.com.br
Deployment: production/web-app
All replicas available: 3/3
```

## 🚀 Como Usar

### 1. Configurar ntfy

Você pode usar o serviço público (ntfy.sh) ou self-hosted:

**Opção A - Serviço Público (padrão):**
```bash
# Apenas configure o tópico no values.yaml
# Por padrão usa: https://ntfy.sh/k8s-cluster-monitor
```

**Opção B - Self-hosted:**
```yaml
# values.yaml
ntfy:
  url: "https://ntfy.kube.chalkan3.com.br"
  topic: "cluster-alerts"
```

### 2. Instalar ntfy App

No seu celular/desktop:
- Android: https://play.google.com/store/apps/details?id=io.heckel.ntfy
- iOS: https://apps.apple.com/us/app/ntfy/id1625396347
- Web: https://ntfy.sh

Inscreva-se no tópico: `k8s-cluster-monitor` (ou o configurado)

### 3. Deploy do Monitor

```bash
# Build e push da imagem
cd /Users/chalkan3/.projects/kubernetes/helmfile/charts/cluster-monitor/docker
chmod +x build.sh
./build.sh

# Deploy via Helm/ArgoCD (em desenvolvimento)
```

## 🧪 Testar Notificações

Após deploy, teste enviando uma requisição para o endpoint `/test`:

```bash
kubectl port-forward -n cluster-monitor svc/monitor 8080:8080

curl -X POST http://localhost:8080/test
```

Você deve receber uma notificação de teste no ntfy!

## 📊 Arquitetura

```
┌─────────────────┐
│  Kubernetes     │
│  API Server     │
└────────┬────────┘
         │ Events
         │
    ┌────▼────────────────┐
    │ Knative Eventing    │
    │ ApiServerSource     │
    └────┬────────────────┘
         │ CloudEvents
         │
    ┌────▼────────────────┐
    │ Cluster Monitor     │
    │ (Knative Service)   │
    └────┬────────────────┘
         │ HTTP POST
         │
    ┌────▼────────────────┐
    │ ntfy.sh             │
    │ (Notification Svc)  │
    └────┬────────────────┘
         │ Push Notifications
         │
    ┌────▼────────────────┐
    │ Your Devices        │
    │ 📱 💻 🖥️            │
    └─────────────────────┘
```

## 🛠️ Configurações Avançadas

### Filtrar Namespaces

Edite `monitor.py` para adicionar filtros:

```python
# Ignorar namespaces específicos
IGNORED_NAMESPACES = ['kube-system', 'kube-public']

if namespace in IGNORED_NAMESPACES:
    return True
```

### Customizar Prioridades

```python
# Ajustar prioridades
send_ntfy_notification(
    title="Custom Alert",
    message="Message",
    priority="max",  # max, high, default, low, min
    tags=["warning", "fire"]  # emojis
)
```

### Tags/Emojis Disponíveis

Veja lista completa: https://ntfy.sh/docs/emojis/

Exemplos úteis:
- `warning`, `rotating_light`: Alertas
- `white_check_mark`: Sucesso
- `skull`: Falhas críticas
- `hourglass`: Aguardando
- `fire`: Urgente
- `information_source`: Informação

## 📝 Próximos Passos

- [ ] Criar Helm chart completo
- [ ] Adicionar ApiServerSource para cada tipo de recurso
- [ ] Implementar rate limiting de notificações
- [ ] Dashboard web para histórico de eventos
- [ ] Integração com Prometheus para métricas
- [ ] Suporte a múltiplos canais (Slack, Teams, etc)

## 🔗 Links Úteis

- ntfy Documentation: https://ntfy.sh
- Knative Eventing: https://knative.dev/docs/eventing/
- ApiServerSource: https://knative.dev/docs/eventing/sources/apiserversource/
