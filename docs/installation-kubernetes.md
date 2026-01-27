# Eleanor DFIR Platform - Kubernetes Installation Guide

This guide covers deploying Eleanor to Kubernetes using Kustomize.

## Prerequisites

- **Kubernetes**: 1.25+ cluster
- **kubectl**: Configured for your cluster
- **Storage**: StorageClass with dynamic provisioning
- **Ingress**: NGINX Ingress Controller (recommended)
- **Resources**: 16GB RAM, 8 CPU cores minimum across nodes

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/project-eleanor/Eleanor.git
cd Eleanor/deploy/kubernetes
```

### 2. Create Namespace

```bash
kubectl apply -f base/namespace.yaml
```

### 3. Configure Secrets

```bash
# Copy secrets template
cp base/secrets.yaml overlays/production/secrets.yaml

# Edit with your values
nano overlays/production/secrets.yaml
```

Required secrets:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: eleanor-secrets
  namespace: eleanor
type: Opaque
stringData:
  DATABASE_PASSWORD: your_secure_db_password
  SECRET_KEY: your_secure_app_key_minimum_32_chars
  ADMIN_PASSWORD: admin_password_for_first_login
  # Integration API keys (optional)
  IRIS_API_KEY: ""
  OPENCTI_API_KEY: ""
  TIMESKETCH_API_KEY: ""
  SHUFFLE_API_KEY: ""
```

### 4. Configure Ingress

Edit `base/ingress.yaml`:
```yaml
spec:
  rules:
    - host: eleanor.yourdomain.com  # Change this
```

### 5. Deploy

```bash
# Development deployment
kubectl apply -k overlays/development

# Production deployment
kubectl apply -k overlays/production
```

### 6. Monitor Deployment

```bash
# Watch pods
kubectl get pods -n eleanor -w

# Check deployment status
kubectl rollout status deployment/backend -n eleanor
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Ingress                               │
│                   (eleanor.domain.com)                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Frontend │      │ Backend  │      │ Backend  │
    │ (nginx)  │      │ Pod 1    │      │ Pod 2    │
    └──────────┘      └────┬─────┘      └────┬─────┘
                           │                 │
                           └────────┬────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
    ┌──────────┐           ┌──────────────┐           ┌───────────┐
    │ PostgreSQL│           │ Elasticsearch │           │   Redis   │
    │(StatefulSet)│         │ (StatefulSet) │           │(Deployment)│
    └──────────┘           └──────────────┘           └───────────┘
```

## Configuration

### ConfigMap

Edit `base/configmap.yaml` for application settings:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: eleanor-config
  namespace: eleanor
data:
  DEBUG: "false"
  LOG_LEVEL: "INFO"
  ELASTICSEARCH_INDEX_PREFIX: "eleanor"
  RATE_LIMIT_ENABLED: "true"
  # Integration URLs
  IRIS_URL: "http://iris-web.eleanor.svc:8000"
  VELOCIRAPTOR_URL: "https://velociraptor.eleanor.svc:8001"
```

### Resource Limits

Production resource recommendations in `overlays/production/kustomization.yaml`:

```yaml
patches:
  - patch: |
      - op: replace
        path: /spec/template/spec/containers/0/resources
        value:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
    target:
      kind: Deployment
      name: backend
```

### Horizontal Pod Autoscaler

The backend includes HPA configuration:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Pod Disruption Budgets

PDBs ensure availability during updates:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: eleanor-backend-pdb
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app.kubernetes.io/name: backend
```

## TLS/SSL Configuration

### Using cert-manager

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@yourdomain.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
EOF
```

Update ingress for TLS:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: eleanor-ingress
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  tls:
    - hosts:
        - eleanor.yourdomain.com
      secretName: eleanor-tls
  rules:
    - host: eleanor.yourdomain.com
      # ...
```

## Monitoring

### Prometheus Metrics

Backend exposes metrics at `/metrics`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: eleanor-backend
  namespace: eleanor
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: backend
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

### Health Checks

```bash
# Check pods
kubectl get pods -n eleanor

# Check services
kubectl get svc -n eleanor

# Check ingress
kubectl get ingress -n eleanor

# View logs
kubectl logs -f deployment/backend -n eleanor

# Check events
kubectl get events -n eleanor --sort-by='.lastTimestamp'
```

## Troubleshooting

### Pod Not Starting

```bash
# Describe pod for events
kubectl describe pod <pod-name> -n eleanor

# Check init container logs
kubectl logs <pod-name> -c wait-for-postgres -n eleanor

# Common issues:
# - ImagePullBackOff: Check image registry credentials
# - Pending: Check PVC binding and node resources
# - CrashLoopBackOff: Check application logs
```

### Database Connection Issues

```bash
# Test PostgreSQL connectivity
kubectl run pg-test --rm -it --image=postgres:16-alpine -n eleanor -- \
  psql "postgresql://eleanor:$PASSWORD@postgres:5432/eleanor" -c "SELECT 1"
```

### Elasticsearch Issues

```bash
# Check cluster health
kubectl exec -it elasticsearch-0 -n eleanor -- \
  curl localhost:9200/_cluster/health?pretty

# Check indices
kubectl exec -it elasticsearch-0 -n eleanor -- \
  curl localhost:9200/_cat/indices
```

### Reset Deployment

```bash
# Delete all resources
kubectl delete -k overlays/production

# Delete PVCs (WARNING: data loss)
kubectl delete pvc --all -n eleanor

# Redeploy
kubectl apply -k overlays/production
```

## Upgrading

```bash
# Update image tags in kustomization.yaml
nano overlays/production/kustomization.yaml

# Apply changes
kubectl apply -k overlays/production

# Watch rollout
kubectl rollout status deployment/backend -n eleanor

# Rollback if needed
kubectl rollout undo deployment/backend -n eleanor
```

## Multi-Cluster / HA Setup

For high availability across zones:

1. Use StatefulSets with multiple replicas for databases
2. Configure Elasticsearch cluster mode
3. Use Redis Sentinel or Redis Cluster
4. Deploy backend across multiple availability zones
5. Use external load balancer with health checks

## Next Steps

1. Access Eleanor via the Ingress URL
2. Complete initial setup wizard
3. Configure integrations in Settings
4. See [Quick Start Guide](quickstart.md) for first investigation
