# Kubernetes GitOps Infrastructure

[![ArgoCD](https://img.shields.io/badge/GitOps-ArgoCD-orange)](https://argoproj.github.io/cd/)
[![Knative](https://img.shields.io/badge/Serverless-Knative-blue)](https://knative.dev/)
[![Harbor](https://img.shields.io/badge/Registry-Harbor-60B932)](https://goharbor.io/)
[![RabbitMQ](https://img.shields.io/badge/Messaging-RabbitMQ-FF6600)](https://www.rabbitmq.com/)

Complete GitOps infrastructure for Kubernetes using ArgoCD, Helmfile, Knative Serving, Harbor Registry, RabbitMQ, and custom monitoring services.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Components](#components)
  - [RabbitMQ](#rabbitmq)
  - [Harbor Registry](#harbor-registry)
  - [Knative](#knative)
  - [Monitoring Services](#monitoring-services)
- [Repository Structure](#repository-structure)
- [Deployment](#deployment)
- [Monitoring & Observability](#monitoring--observability)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

## 🎯 Overview

This repository provides a production-ready GitOps infrastructure for Kubernetes with:

- **Declarative Infrastructure**: Everything defined as code using GitOps principles
- **Automated Deployments**: ArgoCD continuously syncs from Git to cluster
- **Serverless Platform**: Knative Serving for event-driven applications
- **Container Registry**: Private Harbor registry for container images
- **Message Broker**: RabbitMQ for reliable message queuing
- **Smart Monitoring**: Six custom Knative-based monitoring services with ntfy notifications

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          ArgoCD                                  │
│                     (GitOps Controller)                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼─────┐   ┌────▼─────┐   ┌────▼──────────┐
│ RabbitMQ │   │  Harbor  │   │    Knative    │
│ Cluster  │   │ Registry │   │    Serving    │
└──────────┘   └──────────┘   └───────┬───────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
            ┌───────▼────────┐  ┌──────▼──────┐  ┌──────▼──────┐
            │ Pod Restart    │  │   Health    │  │   Scaler    │
            │   Tracker      │  │   Check     │  │   Advisor   │
            └────────────────┘  └─────────────┘  └─────────────┘
                    │                  │                  │
            ┌───────▼────────┐  ┌──────▼──────┐  ┌──────▼──────┐
            │  PVC Storage   │  │  Node Disk  │  │    Drift    │
            │   Monitor      │  │   Monitor   │  │  Detector   │
            └────────────────┘  └─────────────┘  └─────────────┘
                                       │
                              ┌────────▼─────────┐
                              │  ntfy.sh Push    │
                              │  Notifications   │
                              └──────────────────┘
```

## ✅ Prerequisites

- Kubernetes cluster (v1.28+)
- ArgoCD installed and configured
- ArgoCD Helmfile plugin (for Helmfile-based deployments)
- kubectl CLI configured
- Node labels: `workload=tools` for infrastructure components
- (Optional) GitHub CLI (`gh`) for repository mirroring

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/kubernetes-gitops-infrastructure.git
cd kubernetes-gitops-infrastructure
```

### 2. Label Nodes for Infrastructure

```bash
# List nodes
kubectl get nodes

# Label nodes for infrastructure workloads
kubectl label nodes <node-name> workload=tools

# Verify labels
kubectl get nodes --show-labels | grep tools
```

### 3. Deploy Everything via ArgoCD

```bash
# Apply the root Application (App of Apps pattern)
kubectl apply -f argocd/root-app.yaml

# Check deployment status
kubectl get applications -n argocd

# Watch pods coming up
watch kubectl get pods -A
```

## 📦 Components

### RabbitMQ

Enterprise-grade message broker for reliable asynchronous communication.

**Configuration:**
- **Replicas**: 1
- **Persistence**: 8Gi PVC
- **Metrics**: Enabled (Prometheus compatible)
- **NodeSelector**: `workload=tools`
- **Ports**:
  - AMQP: `5672`
  - Management UI: `15672`

**Access:**

```bash
# Port-forward to Management UI
kubectl port-forward -n rabbitmq svc/rabbitmq 15672:15672

# Open browser: http://localhost:15672
# Username: admin
# Password: rabbitmq-password (⚠️ change in production)
```

**Credentials:**
- Username: `admin`
- Password: `rabbitmq-password` ⚠️ **Change in production!**

### Harbor Registry

Private container registry with vulnerability scanning, image signing, and RBAC.

**Configuration:**
- **Access Method**: Ingress (harbor.kube.chalkan3.com.br)
- **Persistence**: Enabled
- **Components**: Portal, Core, Registry, JobService, Trivy scanner
- **NodeSelector**: `workload=tools`

**Access:**

```bash
# Via Ingress (production)
https://harbor.kube.chalkan3.com.br

# Via Port-forward (development)
kubectl port-forward -n harbor svc/harbor 8080:80
# Open: http://localhost:8080
```

**Credentials:**
- Username: `admin`
- Password: `Harbor12345` ⚠️ **Change in production!**

**Using Harbor:**

```bash
# Login to Harbor
docker login harbor.kube.chalkan3.com.br

# Tag and push image
docker tag myapp:latest harbor.kube.chalkan3.com.br/library/myapp:latest
docker push harbor.kube.chalkan3.com.br/library/myapp:latest

# Create pull secret for Kubernetes
kubectl create secret docker-registry harbor-registry \
  --docker-server=harbor.kube.chalkan3.com.br \
  --docker-username=admin \
  --docker-password=Harbor12345 \
  --namespace=<your-namespace>
```

**Features:**
- 🔒 Vulnerability scanning with Trivy
- ✍️ Image signing and content trust
- 👥 RBAC with fine-grained permissions
- 🔄 Multi-registry replication
- 🪝 Webhook notifications
- 🗑️ Automated garbage collection

### Knative

Serverless platform for building, deploying, and managing modern cloud-native applications.

**Components:**
- **Knative Serving**: Deploy and scale serverless containers
- **Knative Eventing**: Event-driven architecture support
- **Kourier**: Lightweight ingress controller

**Deployment Order** (via ArgoCD sync waves):
1. Wave 1: Serving & Eventing CRDs
2. Wave 2: Serving & Eventing Core
3. Wave 3: Kourier Ingress
4. Wave 4: Configuration

**Verify Installation:**

```bash
# Check Knative Serving
kubectl get pods -n knative-serving

# Check Kourier
kubectl get pods -n kourier-system

# Check Knative Eventing
kubectl get pods -n knative-eventing
```

**Example Service:**

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: hello-world
spec:
  template:
    spec:
      containers:
        - image: gcr.io/knative-samples/helloworld-go
          ports:
            - containerPort: 8080
          env:
            - name: TARGET
              value: "Kubernetes"
```

### Monitoring Services

Six custom Knative-based monitoring services that send push notifications via ntfy.sh.

All services are:
- ✅ Serverless (Knative Serving)
- ✅ Auto-scaling (scale-to-zero)
- ✅ GitOps managed (ArgoCD)
- ✅ Scheduled via CronJobs
- ✅ Push notifications (ntfy.sh)

#### 1. Pod Restart Tracker

Monitors pod restarts across the cluster and alerts on excessive restarts.

- **Namespace**: `pod-restart-tracker`
- **Schedule**: Every 5 minutes
- **Threshold**: Alerts if pod restarted ≥3 times
- **Notifications**: ntfy topic `k8s-pod-restarts`

**What it monitors:**
- All pods cluster-wide
- Restart counts and reasons
- Container exit codes
- Recent restart patterns

**Use cases:**
- Detect crashlooping pods
- Identify stability issues
- Monitor application health

#### 2. Health Check

Comprehensive cluster health monitoring with HTTP endpoint checks.

- **Namespace**: `health-check`
- **Schedule**: Every 10 minutes
- **Checks**: Node status, pod health, resource usage
- **Notifications**: ntfy topic `k8s-health-check`

**What it monitors:**
- Node conditions (Ready, DiskPressure, MemoryPressure)
- Pod phase and readiness
- System component health
- Resource availability

**Use cases:**
- Overall cluster health status
- Proactive issue detection
- Infrastructure monitoring

#### 3. Scaler Advisor

AI-powered recommendations for resource optimization and scaling.

- **Namespace**: `scaler-advisor`
- **Schedule**: Every 30 minutes
- **Analysis**: CPU/Memory utilization patterns
- **Notifications**: ntfy topic `k8s-scaler-advisor`

**What it monitors:**
- Resource requests vs actual usage
- Underutilized pods
- Overcommitted resources
- Scaling opportunities

**Recommendations:**
- Increase/decrease replicas
- Adjust resource requests/limits
- Cost optimization suggestions

**Use cases:**
- Resource optimization
- Cost reduction
- Performance tuning

#### 4. PVC Storage Monitor

Monitors Persistent Volume Claims to prevent disk space exhaustion.

- **Namespace**: `pvc-monitor`
- **Schedule**: Every 30 minutes
- **Thresholds**:
  - ⚠️ Warning: 80% full
  - 🚨 Critical: 90% full
- **Notifications**: ntfy topic `k8s-pvc-monitor`

**What it monitors:**
- PVC disk usage across all namespaces
- Storage consumption trends
- Volume capacity planning

**Use cases:**
- Prevent "disk full" incidents
- Storage capacity planning
- Database volume monitoring

#### 5. Node Disk Space Monitor

Monitors disk space on Kubernetes nodes to prevent node-level issues.

- **Namespace**: `node-disk-monitor`
- **Schedule**: Every hour
- **Thresholds**:
  - ⚠️ Warning: 80% full
  - 🚨 Critical: 90% full
- **Notifications**: ntfy topic `k8s-node-disk-monitor`

**What it monitors:**
- Root filesystem usage
- `/var/lib/containerd` or `/var/lib/docker`
- Image cache size
- Node disk I/O

**Use cases:**
- Prevent node evictions
- Container image cleanup
- Node maintenance planning

#### 6. Deployment Drift Detector

Ensures GitOps compliance by detecting manual changes to cluster resources.

- **Namespace**: `drift-detector`
- **Schedule**: Every 15 minutes
- **Detection**: Out-of-sync resources
- **Notifications**: ntfy topic `k8s-drift-detector`

**What it monitors:**
- ArgoCD application sync status
- Resources missing ArgoCD labels
- Manual `kubectl apply` changes
- Degraded applications

**Drift types detected:**
- Configuration changes
- Unmanaged resources
- Out-of-sync deployments

**Use cases:**
- GitOps compliance enforcement
- Change tracking
- Security audit trail
- Prevent configuration drift

## 📁 Repository Structure

```
.
├── README.md                              # This file
├── helmfile.yaml                          # Helmfile configuration
├── values/
│   └── rabbitmq-values.yaml              # RabbitMQ custom values
├── argocd/
│   ├── root-app.yaml                     # Root Application (App of Apps)
│   └── apps/
│       ├── application.yaml              # RabbitMQ Application
│       ├── knative-serving.yaml          # Knative Serving
│       ├── knative-eventing.yaml         # Knative Eventing
│       ├── kourier.yaml                  # Kourier Ingress
│       ├── knative-config.yaml           # Knative configuration
│       ├── harbor.yaml                   # Harbor Registry
│       ├── cert-automation.yaml          # Certificate automation
│       ├── pod-restart-tracker.yaml      # Pod restart monitoring
│       ├── health-check.yaml             # Cluster health monitoring
│       ├── scaler-advisor.yaml           # Resource optimization
│       ├── pvc-monitor.yaml              # PVC storage monitoring
│       ├── node-disk-monitor.yaml        # Node disk monitoring
│       └── drift-detector.yaml           # GitOps drift detection
├── knative/                              # Knative manifests (Kustomize)
│   ├── serving-crds/
│   ├── serving-core/
│   ├── eventing-crds/
│   ├── eventing-core/
│   ├── kourier/
│   └── config/
└── charts/                               # Helm charts for monitoring services
    ├── pod-restart-tracker/
    │   ├── Chart.yaml
    │   ├── templates/
    │   │   ├── service.yaml              # Knative Service
    │   │   ├── rbac.yaml                 # RBAC permissions
    │   │   └── apiserversource.yaml      # Event source
    │   └── docker/
    │       ├── Dockerfile
    │       └── pod_restart_tracker.py    # Python application
    ├── health-check/
    │   ├── Chart.yaml
    │   ├── templates/
    │   └── docker/
    ├── scaler-advisor/
    │   ├── Chart.yaml
    │   ├── templates/
    │   └── docker/
    ├── pvc-monitor/
    │   ├── Chart.yaml
    │   ├── templates/
    │   │   ├── service.yaml
    │   │   ├── rbac.yaml
    │   │   └── cronjob-trigger.yaml      # CronJob trigger
    │   └── docker/
    ├── node-disk-monitor/
    │   ├── Chart.yaml
    │   ├── templates/
    │   └── docker/
    ├── drift-detector/
    │   ├── Chart.yaml
    │   ├── templates/
    │   └── docker/
    └── cert-automation/
        ├── Chart.yaml
        ├── templates/
        └── docker/
```

## 🚢 Deployment

### Manual Deployment with Helmfile

```bash
# Sync all releases
helmfile sync

# Preview changes
helmfile diff

# Deploy specific release
helmfile -l name=rabbitmq sync
```

### GitOps Deployment with ArgoCD

#### Deploy Everything (Recommended)

```bash
# Apply root Application
kubectl apply -f argocd/root-app.yaml

# Monitor deployment
kubectl get applications -n argocd
argocd app list
argocd app sync root
```

#### Deploy Individual Components

```bash
# RabbitMQ
kubectl apply -f argocd/apps/application.yaml

# Harbor
kubectl apply -f argocd/apps/harbor.yaml

# Knative Stack
kubectl apply -f argocd/apps/knative-serving.yaml
kubectl apply -f argocd/apps/kourier.yaml

# Monitoring Services
kubectl apply -f argocd/apps/pod-restart-tracker.yaml
kubectl apply -f argocd/apps/health-check.yaml
kubectl apply -f argocd/apps/scaler-advisor.yaml
kubectl apply -f argocd/apps/pvc-monitor.yaml
kubectl apply -f argocd/apps/node-disk-monitor.yaml
kubectl apply -f argocd/apps/drift-detector.yaml
```

### Verify Deployment

```bash
# Check all ArgoCD applications
kubectl get applications -n argocd

# Check all namespaces
kubectl get pods -A | grep -E "rabbitmq|harbor|knative|restart-tracker|health-check|scaler|pvc-monitor|node-disk|drift"

# Check Knative services
kubectl get ksvc -A
```

## 📊 Monitoring & Observability

### ntfy.sh Notifications

All monitoring services send push notifications to ntfy.sh. Subscribe to receive alerts:

```bash
# Subscribe via ntfy.sh web interface
https://ntfy.sh/k8s-pod-restarts
https://ntfy.sh/k8s-health-check
https://ntfy.sh/k8s-scaler-advisor
https://ntfy.sh/k8s-pvc-monitor
https://ntfy.sh/k8s-node-disk-monitor
https://ntfy.sh/k8s-drift-detector

# Subscribe via ntfy CLI
ntfy subscribe k8s-pod-restarts

# Subscribe via mobile app
# Download ntfy app from App Store/Play Store
# Add topics: k8s-pod-restarts, k8s-health-check, etc.
```

### Manual Triggers

Trigger monitoring checks manually:

```bash
# Trigger pod restart check
kubectl run -it --rm curl --image=curlimages/curl -- \
  curl -X POST http://pod-restart-tracker.pod-restart-tracker.svc.cluster.local/check

# Trigger health check
kubectl run -it --rm curl --image=curlimages/curl -- \
  curl -X POST http://health-check.health-check.svc.cluster.local/check

# Trigger drift detection
kubectl run -it --rm curl --image=curlimages/curl -- \
  curl -X POST http://drift-detector.drift-detector.svc.cluster.local/check
```

### View Service Logs

```bash
# Pod Restart Tracker logs
kubectl logs -n pod-restart-tracker -l serving.knative.dev/service=pod-restart-tracker

# Health Check logs
kubectl logs -n health-check -l serving.knative.dev/service=health-check

# Scaler Advisor logs
kubectl logs -n scaler-advisor -l serving.knative.dev/service=scaler-advisor

# PVC Monitor logs
kubectl logs -n pvc-monitor -l serving.knative.dev/service=pvc-monitor

# Node Disk Monitor logs
kubectl logs -n node-disk-monitor -l serving.knative.dev/service=node-disk-monitor

# Drift Detector logs
kubectl logs -n drift-detector -l serving.knative.dev/service=drift-detector
```

### Prometheus Metrics

RabbitMQ exports Prometheus metrics:

```bash
# Port-forward to RabbitMQ metrics
kubectl port-forward -n rabbitmq svc/rabbitmq 15692:15692

# Scrape metrics
curl http://localhost:15692/metrics
```

## 🔒 Security

### Secret Management

⚠️ **Default credentials MUST be changed for production!**

**Current defaults:**
- RabbitMQ: `admin` / `rabbitmq-password`
- Harbor: `admin` / `Harbor12345`

**Recommended secret management:**

```bash
# Option 1: Sealed Secrets
kubectl create secret generic rabbitmq-credentials \
  --from-literal=username=admin \
  --from-literal=password=<strong-password> \
  --dry-run=client -o yaml | \
  kubeseal -o yaml > sealed-rabbitmq-credentials.yaml

# Option 2: External Secrets Operator
# Define ExternalSecret CRD pointing to Vault/AWS Secrets Manager

# Option 3: ArgoCD Vault Plugin
# Use argocd-vault-plugin to inject secrets at sync time
```

### RBAC

All monitoring services use least-privilege RBAC:

```yaml
# Example: Pod Restart Tracker RBAC
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-restart-tracker
rules:
- apiGroups: [""]
  resources: ["pods", "events"]
  verbs: ["get", "list", "watch"]
```

### Network Policies

Apply network policies to restrict traffic:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: monitoring-egress
  namespace: pod-restart-tracker
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 443  # ntfy.sh HTTPS
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Pods in Pending State

**Symptom:** Pods stuck in Pending state

**Diagnosis:**
```bash
kubectl describe pod <pod-name> -n <namespace>
```

**Common causes:**
- Insufficient CPU/Memory resources
- Missing node labels (`workload=tools`)
- No nodes match node selectors

**Solution:**
```bash
# Check node resources
kubectl describe nodes | grep -A 5 "Allocated resources"

# Add missing labels
kubectl label nodes <node-name> workload=tools
```

#### 2. Image Pull Errors

**Symptom:** `ImagePullBackOff` or `ErrImagePull`

**Diagnosis:**
```bash
kubectl describe pod <pod-name> -n <namespace>
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

**Solution:**
```bash
# Verify imagePullSecrets
kubectl get secret harbor-registry -n <namespace>

# Recreate pull secret
kubectl delete secret harbor-registry -n <namespace>
kubectl create secret docker-registry harbor-registry \
  --docker-server=harbor.kube.chalkan3.com.br \
  --docker-username=admin \
  --docker-password=Harbor12345 \
  --namespace=<namespace>
```

#### 3. ArgoCD Sync Failures

**Symptom:** Application shows `OutOfSync` or `Degraded`

**Diagnosis:**
```bash
argocd app get <app-name>
kubectl describe application <app-name> -n argocd
```

**Solution:**
```bash
# Force refresh
argocd app refresh <app-name>

# Hard refresh (bypass cache)
argocd app refresh <app-name> --hard

# Force sync
argocd app sync <app-name> --force
```

#### 4. Monitoring Services Not Sending Notifications

**Symptom:** No ntfy notifications received

**Diagnosis:**
```bash
# Check service logs
kubectl logs -n pod-restart-tracker -l serving.knative.dev/service=pod-restart-tracker --tail=50

# Test ntfy connectivity
kubectl run -it --rm curl --image=curlimages/curl -- \
  curl -X POST https://ntfy.sh/k8s-test -d "Test message"
```

**Solution:**
```bash
# Verify NTFY_URL environment variable
kubectl get ksvc pod-restart-tracker -n pod-restart-tracker -o yaml | grep -A 5 env

# Manual trigger to test
kubectl run -it --rm curl --image=curlimages/curl -- \
  curl -X POST http://pod-restart-tracker.pod-restart-tracker.svc.cluster.local/check
```

### Debug Commands

```bash
# Check all resources in namespace
kubectl get all -n <namespace>

# Describe Knative Service
kubectl describe ksvc <service-name> -n <namespace>

# Check CronJob schedule
kubectl get cronjobs -n <namespace>

# View recent events
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | tail -20

# Port-forward for direct testing
kubectl port-forward -n <namespace> svc/<service-name> 8080:8080
curl http://localhost:8080/health
curl -X POST http://localhost:8080/check
```

## 📚 Additional Resources

### Official Documentation

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Knative Documentation](https://knative.dev/docs/)
- [Harbor Documentation](https://goharbor.io/docs/)
- [RabbitMQ Documentation](https://www.rabbitmq.com/documentation.html)
- [Helmfile Documentation](https://helmfile.readthedocs.io/)

### Best Practices

- **GitOps**: Never make manual changes with `kubectl apply`
- **Secrets**: Use external secret management (Vault, Sealed Secrets)
- **Monitoring**: Subscribe to all ntfy notification channels
- **Backup**: Regularly backup PVCs, especially RabbitMQ and Harbor
- **Updates**: Keep Knative and ArgoCD updated for security patches

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add documentation
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License.

## 🙋 Support

For issues and questions:
- Open an issue on GitHub
- Check the [Troubleshooting](#troubleshooting) section
- Review ArgoCD application status: `argocd app list`

---

**Made with ❤️ for Kubernetes GitOps**
