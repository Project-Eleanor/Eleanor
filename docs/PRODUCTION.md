# Eleanor Production Deployment Guide

This guide covers production deployment, security hardening, and operational best practices for Eleanor DFIR Platform.

## Table of Contents

- [Pre-Deployment Checklist](#pre-deployment-checklist)
- [Security Hardening](#security-hardening)
- [Performance Tuning](#performance-tuning)
- [High Availability](#high-availability)
- [Monitoring & Alerting](#monitoring--alerting)
- [Backup & Recovery](#backup--recovery)
- [Maintenance Procedures](#maintenance-procedures)
- [Compliance Considerations](#compliance-considerations)

---

## Pre-Deployment Checklist

### Infrastructure Requirements

| Component | Minimum | Recommended | Enterprise |
|-----------|---------|-------------|------------|
| CPU | 8 cores | 16 cores | 32+ cores |
| RAM | 16 GB | 32 GB | 64+ GB |
| Storage | 500 GB SSD | 2 TB NVMe | 10+ TB NVMe |
| Network | 1 Gbps | 10 Gbps | 10+ Gbps |

### Software Prerequisites

```bash
# Verify Docker version
docker --version  # 24.0+

# Verify Docker Compose
docker compose version  # 2.20+

# Verify OpenSSL
openssl version  # 1.1.1+
```

### Network Requirements

| Port | Service | Internal/External |
|------|---------|-------------------|
| 443 | HTTPS | External |
| 80 | HTTP redirect | External |
| 5432 | PostgreSQL | Internal only |
| 9200 | Elasticsearch | Internal only |
| 6379 | Redis | Internal only |

---

## Security Hardening

### Automated Hardening

Run the security hardening script:

```bash
# Check current security posture
./scripts/security-hardening.sh --check-only

# Apply security fixes
sudo ./scripts/security-hardening.sh
```

### Manual Security Checklist

#### 1. Environment Configuration

```bash
# .env security settings
DEBUG=false
SAM_ALLOW_REGISTRATION=false
JWT_EXPIRE_MINUTES=60  # 1 hour max
CORS_ORIGINS=https://your-domain.com
```

#### 2. File Permissions

```bash
# Secure .env file
chmod 600 .env

# Secure certificates
chmod 700 certificates/
chmod 600 certificates/*.key

# Secure backups
chmod 700 backups/
```

#### 3. SSL/TLS Configuration

For production, use proper SSL certificates:

```bash
# Option 1: Let's Encrypt (recommended for public deployments)
certbot certonly --standalone -d your-domain.com

# Option 2: Internal CA
./scripts/generate-certs.sh --hostname your-domain.com --ca /path/to/ca.crt

# Option 3: Self-signed (OVA default, update for production)
./scripts/generate-certs.sh --hostname your-domain.com --days 365
```

#### 4. Firewall Configuration

```bash
# UFW (Ubuntu)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# firewalld (RHEL/CentOS)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

#### 5. Docker Security

```yaml
# docker-compose.prod.yml additions
services:
  backend:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
```

#### 6. Database Security

```bash
# PostgreSQL configuration (in docker-compose.prod.yml)
environment:
  - POSTGRES_HOST_AUTH_METHOD=scram-sha-256

# Elasticsearch security
environment:
  - xpack.security.enabled=true
  - ELASTIC_PASSWORD=${ELASTIC_PASSWORD}
```

### Security Headers

The nginx configuration includes security headers:

```nginx
# Already configured in nginx.conf
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; ..." always;
```

---

## Performance Tuning

### Elasticsearch Optimization

```yaml
# Based on available RAM
environment:
  # 8GB RAM system
  - ES_JAVA_OPTS=-Xms2g -Xmx2g

  # 16GB RAM system
  - ES_JAVA_OPTS=-Xms4g -Xmx4g

  # 32GB+ RAM system
  - ES_JAVA_OPTS=-Xms8g -Xmx8g

# Never allocate more than 50% of total RAM to ES heap
# Never exceed 31GB heap (compressed oops limit)
```

### PostgreSQL Optimization

```yaml
# docker-compose.prod.yml
postgres:
  command:
    - "postgres"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=1GB"
    - "-c"
    - "effective_cache_size=3GB"
    - "-c"
    - "work_mem=64MB"
    - "-c"
    - "maintenance_work_mem=256MB"
```

### Redis Optimization

```yaml
redis:
  command:
    - "redis-server"
    - "--maxmemory"
    - "1gb"
    - "--maxmemory-policy"
    - "volatile-lru"
```

### Evidence Storage

For large evidence files, consider:

```yaml
volumes:
  evidence_storage:
    driver: local
    driver_opts:
      type: nfs
      o: addr=nas.example.com,rw,nolock
      device: ":/exports/evidence"
```

---

## High Availability

### Multi-Node PostgreSQL

For HA PostgreSQL, consider:

1. **PostgreSQL Replication** with streaming replication
2. **PgBouncer** for connection pooling
3. **Patroni** for automatic failover

### Elasticsearch Cluster

```yaml
# docker-compose.ha.yml
elasticsearch-1:
  environment:
    - node.name=es01
    - cluster.name=eleanor-cluster
    - cluster.initial_master_nodes=es01,es02,es03
    - discovery.seed_hosts=es02,es03

elasticsearch-2:
  # Similar configuration for es02

elasticsearch-3:
  # Similar configuration for es03
```

### Load Balancing

For multiple backend instances:

```nginx
upstream backend {
    least_conn;
    server backend-1:8000;
    server backend-2:8000;
    server backend-3:8000;
}
```

---

## Monitoring & Alerting

### Health Checks

```bash
# Automated health check
./scripts/health-check.sh --json

# Prometheus metrics endpoint (if enabled)
curl http://localhost:8000/metrics
```

### Recommended Monitoring Stack

1. **Prometheus** - Metrics collection
2. **Grafana** - Visualization
3. **Alertmanager** - Alert routing

### Key Metrics to Monitor

| Metric | Threshold | Action |
|--------|-----------|--------|
| CPU Usage | > 80% | Scale or investigate |
| Memory Usage | > 85% | Scale or tune |
| Disk Usage | > 80% | Add storage or cleanup |
| ES Cluster Health | Yellow/Red | Investigate immediately |
| API Response Time | > 2s | Investigate performance |
| Failed Logins | > 10/min | Potential attack |

### Log Aggregation

Configure Docker log rotation:

```json
// /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "5"
  }
}
```

---

## Backup & Recovery

### Automated Backups

```bash
# Full backup (daily)
./scripts/backup.sh --compress --include-es

# Database only backup (hourly)
./scripts/backup.sh --db-only

# Backup to remote location
./scripts/backup.sh --output /mnt/backup-nas/eleanor
```

### Backup Retention Policy

| Backup Type | Retention | Frequency |
|-------------|-----------|-----------|
| Full | 30 days | Daily |
| Database | 7 days | Hourly |
| Elasticsearch | 30 days | Daily |
| Evidence | Indefinite | On change |

### Disaster Recovery

1. **RPO (Recovery Point Objective)**: 1 hour maximum data loss
2. **RTO (Recovery Time Objective)**: 4 hours to full recovery

### Recovery Procedure

```bash
# Stop services
docker compose down

# Restore from backup
./scripts/restore.sh --backup /path/to/backup

# Verify integrity
./scripts/health-check.sh

# Start services
docker compose up -d
```

---

## Maintenance Procedures

### Regular Maintenance Schedule

| Task | Frequency | Command |
|------|-----------|---------|
| Health Check | Hourly | `./scripts/health-check.sh` |
| Backup | Daily | `./scripts/backup.sh` |
| Log Rotation | Automatic | Docker handles |
| Security Scan | Weekly | `./scripts/security-hardening.sh -c` |
| Update Check | Weekly | `docker compose pull` |
| Full Update | Monthly | See update procedure |

### Update Procedure

```bash
# 1. Backup
./scripts/backup.sh --compress

# 2. Pull new images
docker compose pull

# 3. Apply updates (zero-downtime for minor versions)
docker compose up -d --no-deps backend
docker compose up -d --no-deps frontend

# 4. Verify
./scripts/health-check.sh

# 5. Run migrations if needed
docker exec eleanor-backend alembic upgrade head
```

### Index Management

```bash
# Elasticsearch index lifecycle management
curl -X PUT "localhost:9200/_ilm/policy/eleanor-policy" -H 'Content-Type: application/json' -d'
{
  "policy": {
    "phases": {
      "hot": {
        "actions": {
          "rollover": {
            "max_size": "50gb",
            "max_age": "30d"
          }
        }
      },
      "delete": {
        "min_age": "90d",
        "actions": {
          "delete": {}
        }
      }
    }
  }
}'
```

---

## Compliance Considerations

### Data Retention

Configure evidence retention based on legal requirements:

| Data Type | Retention Period | Justification |
|-----------|------------------|---------------|
| Case Data | 7 years | Legal requirement |
| Evidence | Per case policy | Legal hold |
| Audit Logs | 1 year | Compliance |
| User Activity | 90 days | Security |

### Audit Logging

Eleanor logs the following for compliance:

- User authentication events
- Case access and modifications
- Evidence uploads and downloads
- Configuration changes
- API access patterns

### Access Controls

1. **Role-Based Access Control (RBAC)** - Built-in
2. **Multi-Factor Authentication** - Via OIDC provider
3. **Session Management** - Configurable timeout
4. **IP Allowlisting** - Via firewall rules

### Chain of Custody

Evidence chain of custody is automatically maintained:

```json
{
  "evidence_id": "...",
  "custody_events": [
    {"action": "uploaded", "user": "analyst1", "timestamp": "..."},
    {"action": "accessed", "user": "analyst2", "timestamp": "..."},
    {"action": "exported", "user": "analyst1", "timestamp": "..."}
  ]
}
```

---

## Troubleshooting Production Issues

### Common Issues

**Services won't start after update**
```bash
# Check for migration issues
docker compose logs backend | grep -i error
docker exec eleanor-backend alembic upgrade head
```

**Elasticsearch cluster red**
```bash
# Check cluster health
curl localhost:9200/_cluster/health?pretty

# Check unassigned shards
curl localhost:9200/_cat/shards?v | grep UNASSIGNED
```

**High memory usage**
```bash
# Check container stats
docker stats --no-stream

# Adjust Elasticsearch heap
# Edit ES_JAVA_OPTS in .env
```

**Database connection errors**
```bash
# Check PostgreSQL
docker exec eleanor-postgres pg_isready

# Check connection pool
docker exec eleanor-backend python -c "from app.database import engine; print(engine.pool.status())"
```

### Emergency Procedures

**Emergency Shutdown**
```bash
docker compose down
```

**Emergency Password Reset**
```bash
./scripts/reset-admin-password.sh
```

**Rollback to Previous Version**
```bash
# Restore from backup
./scripts/restore.sh --backup /path/to/last-good-backup

# Pull specific version
docker compose pull backend:v1.2.3
docker compose up -d
```

---

## Support

- Documentation: `/docs/`
- Troubleshooting: `docs/TROUBLESHOOTING.md`
- Issues: https://github.com/your-org/eleanor/issues
