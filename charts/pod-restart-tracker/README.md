# Pod Restart Tracker

Serviço Knative que monitora reinicializações frequentes de pods no cluster Kubernetes.

## Funcionalidades

- ✅ Detecta pods com muitos restarts (threshold configurável)
- ✅ Calcula taxa de restart por minuto
- ✅ Coleta logs automaticamente antes do crash
- ✅ Analisa padrões de falha
- ✅ Severidade dinâmica (normal/high/max)
- ✅ Histórico em memória com janela de tempo

## Configuração

Variáveis de ambiente:

```yaml
NTFY_URL: https://ntfy.sh
NTFY_TOPIC: k8s-restart-tracker
CLUSTER_NAME: kube.chalkan3.com.br
RESTART_THRESHOLD: 5  # Alertar após N restarts
TIME_WINDOW_MINUTES: 60  # Janela de tempo para análise
```

## Endpoints

- `POST /test` - Teste de notificação
- `GET /health` - Health check
- `GET /stats` - Estatísticas de pods rastreados

## Deploy

```bash
kubectl apply -f templates/
```

## Uso

O serviço recebe eventos de Pods via ApiServerSource e processa automaticamente.

Para testar manualmente:
```bash
kubectl run test -n pod-restart-tracker --image=curlimages/curl --rm -it -- \
  curl -X POST http://pod-restart-tracker.pod-restart-tracker/test
```
