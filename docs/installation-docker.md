# Eleanor DFIR Platform - Docker Installation Guide

This guide covers deploying Eleanor using Docker Compose.

## Prerequisites

- **Docker Engine**: 24.0+ with Docker Compose v2
- **RAM**: 8GB minimum (32GB for full stack)
- **Storage**: 50GB minimum (100GB+ for full stack with data)
- **Ports**: 80/443 (web), 8000 (API)

## Quick Start (Eleanor Only)

Deploy Eleanor with its core dependencies (PostgreSQL, Elasticsearch, Redis):

```bash
# Clone the repository
git clone https://github.com/project-eleanor/Eleanor.git
cd Eleanor

# Create environment file
cp .env.example .env

# Edit .env with your settings
nano .env

# Start services
docker-compose up -d

# Check status
docker-compose ps
```

Access Eleanor at `http://localhost` (or `https://localhost` with SSL configured).

## Environment Configuration

### Required Variables

```bash
# .env file

# Database
POSTGRES_PASSWORD=your_secure_database_password

# Application Security
SECRET_KEY=your-secure-random-key-minimum-32-characters

# Admin User (set on first run)
ADMIN_EMAIL=admin@yourcompany.com
ADMIN_PASSWORD=secure_admin_password
```

### Optional Variables

```bash
# Integrations (configure after initial setup)
VELOCIRAPTOR_URL=https://velociraptor.local:8001
IRIS_URL=http://iris.local:8000
OPENCTI_URL=http://opencti.local:8080
TIMESKETCH_URL=http://timesketch.local:5000
SHUFFLE_URL=http://shuffle.local:5001
```

## Full Stack Deployment

Deploy Eleanor with all integrated services (IRIS, Velociraptor, OpenCTI, Timesketch, Shuffle):

```bash
# Copy full stack environment
cp .env.full.example .env

# Edit with secure passwords
nano .env

# Deploy full stack
docker-compose -f docker-compose.full.yml up -d

# Monitor startup (can take 5-10 minutes)
docker-compose -f docker-compose.full.yml logs -f
```

### Full Stack Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| Eleanor Frontend | 80/443 | Web UI |
| Eleanor API | 8000 | REST API |
| IRIS | 8001 | Case Management |
| Velociraptor | 8002/8003 | Endpoint Collection |
| OpenCTI | 8004 | Threat Intelligence |
| Timesketch | 8005 | Timeline Analysis |
| Shuffle | 8006/8007 | SOAR Platform |

### Resource Requirements

Full stack deployment requires significant resources:

| Component | RAM | CPU | Storage |
|-----------|-----|-----|---------|
| Eleanor Core | 4GB | 2 | 10GB |
| PostgreSQL | 2GB | 1 | 20GB |
| Elasticsearch | 4GB | 2 | 50GB |
| Redis | 1GB | 0.5 | 1GB |
| IRIS | 3GB | 1 | 10GB |
| Velociraptor | 2GB | 1 | 20GB |
| OpenCTI | 6GB | 2 | 20GB |
| Timesketch | 4GB | 1 | 20GB |
| Shuffle | 3GB | 1 | 10GB |
| **Total** | **~32GB** | **~12** | **~160GB** |

## SSL/TLS Configuration

### Self-Signed Certificates (Development)

```bash
# Generate self-signed certificate
mkdir -p deploy/docker/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout deploy/docker/ssl/eleanor.key \
  -out deploy/docker/ssl/eleanor.crt \
  -subj "/CN=eleanor.local"

# Update nginx.conf to use SSL
# Restart frontend
docker-compose restart frontend
```

### Let's Encrypt (Production)

```bash
# Install certbot
apt install certbot

# Obtain certificate
certbot certonly --standalone -d eleanor.yourdomain.com

# Copy certificates
cp /etc/letsencrypt/live/eleanor.yourdomain.com/fullchain.pem deploy/docker/ssl/eleanor.crt
cp /etc/letsencrypt/live/eleanor.yourdomain.com/privkey.pem deploy/docker/ssl/eleanor.key

# Restart
docker-compose restart frontend
```

## Managing Services

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend
```

### Restart Services

```bash
# Single service
docker-compose restart backend

# All services
docker-compose restart
```

### Update to Latest Version

```bash
# Pull latest images
docker-compose pull

# Recreate containers
docker-compose up -d

# Clean old images
docker image prune -f
```

### Backup Data

```bash
# Stop services
docker-compose stop

# Backup volumes
docker run --rm -v eleanor_postgres_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/postgres_backup.tar.gz /data

docker run --rm -v eleanor_elasticsearch_data:/data -v $(pwd):/backup alpine \
  tar czf /backup/elasticsearch_backup.tar.gz /data

# Restart services
docker-compose start
```

## Troubleshooting

### Services Not Starting

```bash
# Check service status
docker-compose ps

# View logs for failed service
docker-compose logs [service-name]

# Common issues:
# - Elasticsearch: needs vm.max_map_count=262144
# - PostgreSQL: check POSTGRES_PASSWORD matches
# - Backend: verify DATABASE_URL format
```

### Elasticsearch Memory Issues

```bash
# Increase vm.max_map_count
sudo sysctl -w vm.max_map_count=262144

# Make permanent
echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
```

### Reset Everything

```bash
# WARNING: This deletes all data
docker-compose down -v
docker-compose up -d
```

## Health Checks

```bash
# Eleanor API
curl -s http://localhost:8000/api/v1/health | jq

# Elasticsearch
curl -s http://localhost:9200/_cluster/health | jq

# PostgreSQL
docker-compose exec postgres pg_isready -U eleanor
```

## Next Steps

1. Access Eleanor at `http://localhost`
2. Complete initial setup wizard
3. Configure integrations in Settings
4. See [Quick Start Guide](quickstart.md) for first investigation
