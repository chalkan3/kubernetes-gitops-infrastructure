# RabbitMQ Application - Desabilitado Temporariamente

## Problema

O RabbitMQ Application está desabilitado porque **TODO O AMBIENTE** não consegue acessar registries públicos externos:

- ❌ Docker Hub (`docker.io`) - não acessível do cluster
- ❌ Quay.io (`quay.io`) - não acessível do cluster
- ❌ Docker Hub - não acessível do host 192.168.1.17 (timeout DNS)
- ❌ Máquina local - Docker daemon não disponível

**Causa raiz**: Problema de conectividade de rede/DNS no ambiente inteiro, não apenas no cluster

## Solução 1: Usar Harbor como Mirror

O Harbor está instalado e funcional no cluster. Para usar o RabbitMQ:

### Pré-requisito: Máquina com Acesso ao Docker Hub

**IMPORTANTE**: Você precisa de uma máquina que tenha:
- ✅ Docker instalado e rodando
- ✅ Conectividade à internet para acessar Docker Hub
- ✅ Conectividade ao Harbor no cluster (10.8.0.13:30002)

⚠️ **Atualmente, nenhuma máquina no ambiente tem acesso ao Docker Hub.**

### 1. De uma máquina COM acesso ao Docker Hub:

```bash
# Pull da imagem
docker pull bitnami/rabbitmq:3.13.7-debian-12-r4

# Tag para Harbor
docker tag bitnami/rabbitmq:3.13.7-debian-12-r4 10.8.0.13:30002/library/rabbitmq:3.13.7-debian-12-r4

# Configurar insecure registry (se necessário)
# Adicionar ao /etc/docker/daemon.json:
{
  "insecure-registries": ["10.8.0.13:30002"]
}
# Reiniciar Docker: sudo systemctl restart docker

# Login no Harbor
docker login 10.8.0.13:30002
# Usuário: admin
# Senha: Harbor12345

# Push para Harbor
docker push 10.8.0.13:30002/library/rabbitmq:3.13.7-debian-12-r4
```

### 2. Atualizar a Application:

Edite `application.yaml.disabled` e mude:

```yaml
image:
  registry: 10.8.0.13:30002
  repository: library/rabbitmq
  tag: 3.13.7-debian-12-r4
```

### 3. Criar ImagePullSecret (se Harbor requer autenticação):

```bash
kubectl create secret docker-registry harbor-registry \
  --docker-server=10.8.0.13:30002 \
  --docker-username=admin \
  --docker-password=Harbor12345 \
  --namespace=rabbitmq

# Adicionar ao application.yaml:
imagePullSecrets:
  - name: harbor-registry
```

### 4. Reabilitar a Application:

```bash
mv application.yaml.disabled application.yaml
git add . && git commit -m "Enable RabbitMQ with Harbor registry" && git push
```

## Solução 2: Resolver Conectividade Externa

Configurar proxy/NAT/firewall para permitir acesso do cluster a registries públicos.

## Status Atual

- Application renomeada para: `application.yaml.disabled`
- Quando reabilitada, o ArgoCD irá gerenciá-la automaticamente via `cluster-apps`

## Acesso ao Harbor

- URL: http://10.8.0.13:30002
- Usuário: admin
- Senha: Harbor12345
