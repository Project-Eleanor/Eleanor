# Eleanor Kubernetes Deployment

Production-ready Kubernetes manifests for deploying Eleanor DFIR platform with auto-scaling capabilities.

## Architecture

```
                                    ┌──────────────────────────────────────────┐
                                    │              Kubernetes Cluster           │
                                    │                                           │
┌─────────┐    ┌──────────┐        │  ┌─────────────────────────────────────┐  │
│  Users  │───►│ Ingress  │───────►│  │           Frontend (HPA)            │  │
└─────────┘    │Controller│        │  │  nginx: 2-8 replicas                │  │
               └──────────┘        │  └──────────────┬──────────────────────┘  │
                                   │                 │                          │
                                   │                 ▼                          │
                                   │  ┌─────────────────────────────────────┐  │
                                   │  │           Backend (HPA)              │  │
                                   │  │  FastAPI: 2-10 replicas             │  │
                                   │  └──────┬──────────────┬───────────────┘  │
                                   │         │              │                   │
                                   │         ▼              ▼                   │
                                   │  ┌────────────┐ ┌─────────────────────┐   │
                                   │  │   Redis    │ │  Celery Workers     │   │
                                   │  │ StatefulSet│ │  (HPA: 2-20)        │   │
                                   │  └────────────┘ └──────┬──────────────┘   │
                                   │                        │                   │
                                   │         ┌──────────────┼──────────────┐    │
                                   │         ▼              ▼              ▼    │
                                   │  ┌────────────┐ ┌────────────┐ ┌────────┐ │
                                   │  │ PostgreSQL │ │Elasticsearch│ │Evidence│ │
                                   │  │ StatefulSet│ │ StatefulSet │ │  PVC   │ │
                                   │  └────────────┘ └────────────┘ └────────┘ │
                                   └───────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Kubernetes cluster (1.25+)
- kubectl configured
- kustomize (optional, kubectl has built-in support)
- NGINX Ingress Controller (for ingress)
- Storage class that supports ReadWriteOnce and ReadWriteMany

### Deploy to Development

```bash
./deploy.sh development deploy
```

### Deploy to Production

```bash
# First, update secrets with secure values
vim overlays/production/secrets.yaml

# Deploy
./deploy.sh production deploy
```

## Structure

```
kubernetes/
├── base/                       # Base manifests
│   ├── namespace.yaml          # Namespace definition
│   ├── configmap.yaml          # Configuration
│   ├── secrets.yaml            # Secrets (template)
│   ├── storage.yaml            # PVCs
│   ├── postgres.yaml           # PostgreSQL StatefulSet
│   ├── elasticsearch.yaml      # Elasticsearch StatefulSet
│   ├── redis.yaml              # Redis StatefulSet
│   ├── backend.yaml            # Backend Deployment + HPA
│   ├── celery.yaml             # Celery Workers + Beat + HPA
│   ├── frontend.yaml           # Frontend Deployment + HPA
│   ├── ingress.yaml            # Ingress + LoadBalancer
│   ├── network-policies.yaml   # Network security
│   └── kustomization.yaml      # Kustomize config
├── overlays/
│   ├── development/            # Dev environment
│   │   └── kustomization.yaml  # Dev overrides
│   └── production/             # Prod environment
│       ├── kustomization.yaml  # Prod overrides
│       └── secrets.yaml        # Prod secrets
├── deploy.sh                   # Deployment script
└── README.md                   # This file
```

## Auto-Scaling Configuration

### Horizontal Pod Autoscaler (HPA)

| Component      | Min | Max | CPU Target | Memory Target |
|----------------|-----|-----|------------|---------------|
| Backend        | 2   | 10  | 70%        | 80%           |
| Celery Workers | 2   | 20  | 60%        | 70%           |
| Frontend       | 2   | 8   | 70%        | 80%           |

### Scale Behavior

- **Scale Up**: Fast (30-60s stabilization), up to 100% increase
- **Scale Down**: Slow (300s stabilization), max 25% decrease

### Manual Scaling

```bash
# Scale backend to 5 replicas
./deploy.sh production scale backend 5

# Scale celery workers to 10 replicas
./deploy.sh production scale celery-worker 10
```

## Resource Requirements

### Minimum (Development)

| Component      | Memory | CPU   | Storage |
|----------------|--------|-------|---------|
| PostgreSQL     | 512Mi  | 250m  | 5Gi     |
| Elasticsearch  | 2Gi    | 500m  | 20Gi    |
| Redis          | 256Mi  | 100m  | 5Gi     |
| Backend        | 256Mi  | 100m  | -       |
| Celery Worker  | 256Mi  | 100m  | -       |
| Frontend       | 64Mi   | 50m   | -       |
| Evidence Store | -      | -     | 50Gi    |

### Recommended (Production)

| Component      | Memory | CPU    | Storage |
|----------------|--------|--------|---------|
| PostgreSQL     | 2Gi    | 1000m  | 50Gi    |
| Elasticsearch  | 8Gi    | 2000m  | 500Gi   |
| Redis          | 1Gi    | 500m   | 5Gi     |
| Backend (x3)   | 4Gi    | 2000m  | -       |
| Celery (x4)    | 8Gi    | 4000m  | -       |
| Frontend (x3)  | 256Mi  | 500m   | -       |
| Evidence Store | -      | -      | 2Ti     |

## Configuration

### Environment Variables

Edit `base/configmap.yaml` for non-sensitive configuration:

```yaml
data:
  API_WORKERS: "4"
  LOG_LEVEL: "INFO"
  ELASTICSEARCH_HOSTS: "http://elasticsearch:9200"
```

### Secrets

Generate secure secrets for production:

```bash
# Generate database password
openssl rand -base64 32

# Generate JWT secret
openssl rand -base64 64

# Update overlays/production/secrets.yaml with generated values
```

### Ingress

Update `base/ingress.yaml` with your domain:

```yaml
spec:
  rules:
    - host: eleanor.yourdomain.com
```

For TLS, uncomment and configure the TLS section:

```yaml
tls:
  - hosts:
      - eleanor.yourdomain.com
    secretName: eleanor-tls
```

## Operations

### View Logs

```bash
# Backend logs
./deploy.sh production logs backend

# Celery worker logs
./deploy.sh production logs celery-worker

# All pods
kubectl -n eleanor logs -l app.kubernetes.io/part-of=eleanor-dfir -f
```

### Port Forwarding (Local Access)

```bash
./deploy.sh production port-forward

# Access at:
# Frontend: http://localhost:8080
# API: http://localhost:8000
```

### Check Status

```bash
./deploy.sh production status
```

### View HPA Status

```bash
kubectl -n eleanor get hpa -w
```

## Monitoring

### Prometheus Metrics

Backend exposes metrics at `/api/v1/metrics`. Add annotations:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/api/v1/metrics"
```

### Recommended Dashboards

- Kubernetes cluster metrics
- Pod resource usage
- HPA scaling events
- Elasticsearch cluster health
- PostgreSQL metrics

## Troubleshooting

### Pods Not Starting

```bash
# Check events
kubectl -n eleanor get events --sort-by=.metadata.creationTimestamp

# Describe pod
kubectl -n eleanor describe pod <pod-name>
```

### Database Connection Issues

```bash
# Check if postgres is ready
kubectl -n eleanor exec -it postgres-0 -- pg_isready -U eleanor

# Check logs
kubectl -n eleanor logs postgres-0
```

### Elasticsearch Issues

```bash
# Check cluster health
kubectl -n eleanor exec -it elasticsearch-0 -- curl localhost:9200/_cluster/health?pretty

# Check logs
kubectl -n eleanor logs elasticsearch-0
```

### Storage Issues

```bash
# Check PVC status
kubectl -n eleanor get pvc

# Check storage class
kubectl get storageclass
```

## Backup & Recovery

### Database Backup

```bash
# Create backup
kubectl -n eleanor exec postgres-0 -- pg_dump -U eleanor eleanor > backup.sql

# Restore
kubectl -n eleanor exec -i postgres-0 -- psql -U eleanor eleanor < backup.sql
```

### Elasticsearch Snapshot

Configure snapshot repository and use Elasticsearch snapshot API.

## Security Considerations

1. **Secrets Management**: Use external secrets manager (HashiCorp Vault, AWS Secrets Manager)
2. **Network Policies**: Enabled by default, restricts pod-to-pod communication
3. **RBAC**: Apply least-privilege service accounts
4. **TLS**: Configure TLS for ingress and internal communication
5. **Image Security**: Use signed images from trusted registry

## Upgrading

```bash
# Update image tags in kustomization.yaml
# Then apply:
./deploy.sh production deploy

# Or rolling update specific deployment:
kubectl -n eleanor rollout restart deployment/backend
```
