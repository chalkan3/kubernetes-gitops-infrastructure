# RabbitMQ Application - Desabilitado Temporariamente

## Problema

O RabbitMQ Application está desabilitado porque o cluster não consegue baixar imagens de registries públicos externos:

- ❌ Docker Hub (`docker.io`) - não acessível
- ❌ Quay.io (`quay.io`) - não acessível

## Solução 1: Usar Harbor como Mirror

O Harbor está instalado e funcional no cluster. Para usar o RabbitMQ:

### 1. De uma máquina com acesso ao Docker Hub:

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
