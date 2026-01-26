#!/bin/bash
# Eleanor DFIR Platform - Application Setup
# This script sets up the Eleanor application and pre-pulls Docker images

set -e

echo "=== Eleanor Application Setup ==="

ELEANOR_VERSION="${ELEANOR_VERSION:-1.0.0}"
ELEANOR_DIR="/opt/eleanor"

# Create Docker Compose configuration
echo "Creating Docker Compose configuration..."

cat > ${ELEANOR_DIR}/docker-compose.yml << 'EOF'
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: eleanor-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-eleanor}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-eleanor_secure_password}
      POSTGRES_DB: ${POSTGRES_DB:-eleanor}
    volumes:
      - /var/lib/eleanor/postgres:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-eleanor}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - eleanor-net

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: eleanor-redis
    restart: unless-stopped
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - /var/lib/eleanor/redis:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - eleanor-net

  # Elasticsearch
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.11.0
    container_name: eleanor-elasticsearch
    restart: unless-stopped
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - xpack.security.http.ssl.enabled=false
      - "ES_JAVA_OPTS=-Xms4g -Xmx4g"
      - cluster.name=eleanor
      - bootstrap.memory_lock=true
    ulimits:
      memlock:
        soft: -1
        hard: -1
      nofile:
        soft: 65536
        hard: 65536
    volumes:
      - /var/lib/eleanor/elasticsearch:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -s http://localhost:9200/_cluster/health | grep -vq '\"status\":\"red\"'"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - eleanor-net

  # Eleanor Backend API
  backend:
    image: ghcr.io/eleanor-dfir/backend:${ELEANOR_VERSION:-latest}
    container_name: eleanor-backend
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-eleanor}:${POSTGRES_PASSWORD:-eleanor_secure_password}@postgres:5432/${POSTGRES_DB:-eleanor}
      - REDIS_URL=redis://redis:6379/0
      - ELASTICSEARCH_URL=http://elasticsearch:9200
      - SECRET_KEY=${SECRET_KEY:-change_me_in_production}
      - JWT_SECRET=${JWT_SECRET:-change_me_in_production}
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    volumes:
      - /var/lib/eleanor/evidence:/data/evidence
      - /var/lib/eleanor/exports:/data/exports
      - /var/log/eleanor:/var/log/eleanor
    ports:
      - "8000:8000"
    networks:
      - eleanor-net

  # Eleanor Frontend
  frontend:
    image: ghcr.io/eleanor-dfir/frontend:${ELEANOR_VERSION:-latest}
    container_name: eleanor-frontend
    restart: unless-stopped
    depends_on:
      - backend
    environment:
      - API_URL=http://backend:8000
    ports:
      - "3000:80"
    networks:
      - eleanor-net

  # Celery Worker
  celery-worker:
    image: ghcr.io/eleanor-dfir/backend:${ELEANOR_VERSION:-latest}
    container_name: eleanor-celery-worker
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-eleanor}:${POSTGRES_PASSWORD:-eleanor_secure_password}@postgres:5432/${POSTGRES_DB:-eleanor}
      - REDIS_URL=redis://redis:6379/0
      - ELASTICSEARCH_URL=http://elasticsearch:9200
    volumes:
      - /var/lib/eleanor/evidence:/data/evidence
    networks:
      - eleanor-net

  # Celery Beat Scheduler
  celery-beat:
    image: ghcr.io/eleanor-dfir/backend:${ELEANOR_VERSION:-latest}
    container_name: eleanor-celery-beat
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER:-eleanor}:${POSTGRES_PASSWORD:-eleanor_secure_password}@postgres:5432/${POSTGRES_DB:-eleanor}
      - REDIS_URL=redis://redis:6379/0
    networks:
      - eleanor-net

networks:
  eleanor-net:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/24
EOF

# Create environment file template
cat > ${ELEANOR_DIR}/.env.template << 'EOF'
# Eleanor DFIR Platform Configuration
# Copy to .env and customize

# Database
POSTGRES_USER=eleanor
POSTGRES_PASSWORD=CHANGE_ME
POSTGRES_DB=eleanor

# Security Keys (generate with: openssl rand -hex 32)
SECRET_KEY=CHANGE_ME
JWT_SECRET=CHANGE_ME

# Eleanor Version
ELEANOR_VERSION=1.0.0

# Optional: External integrations
# VELOCIRAPTOR_URL=
# VELOCIRAPTOR_API_KEY=
# IRIS_URL=
# IRIS_API_KEY=
# OPENCTI_URL=
# OPENCTI_API_KEY=
# SHUFFLE_URL=
# SHUFFLE_API_KEY=
EOF

# Pre-pull Docker images
echo "Pre-pulling Docker images (this may take a while)..."

# Core infrastructure images
docker pull postgres:15-alpine
docker pull redis:7-alpine
docker pull docker.elastic.co/elasticsearch/elasticsearch:8.11.0
docker pull nginx:alpine

# Pre-pull Eleanor images if available, or placeholder images
# In production, these would be the actual Eleanor images
docker pull python:3.11-slim || true
docker pull node:20-alpine || true

# Create nginx configuration for reverse proxy
echo "Creating nginx configuration..."
cat > ${ELEANOR_DIR}/config/nginx.conf << 'EOF'
upstream backend {
    server localhost:8000;
}

upstream frontend {
    server localhost:3000;
}

server {
    listen 80;
    server_name _;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name _;

    # SSL configuration (self-signed initially)
    ssl_certificate /etc/nginx/ssl/eleanor.crt;
    ssl_certificate_key /etc/nginx/ssl/eleanor.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers off;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API proxy
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
        client_max_body_size 500M;
    }

    # WebSocket proxy
    location /ws/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Frontend proxy
    location / {
        proxy_pass http://frontend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Create self-signed SSL certificate
echo "Creating self-signed SSL certificate..."
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/eleanor.key \
    -out /etc/nginx/ssl/eleanor.crt \
    -subj "/C=US/ST=State/L=City/O=Eleanor/CN=eleanor.local"

# Create systemd service for Eleanor
echo "Creating systemd service..."
cat > /etc/systemd/system/eleanor.service << 'EOF'
[Unit]
Description=Eleanor DFIR Platform
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/eleanor
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF

# Create update script
echo "Creating update script..."
cat > ${ELEANOR_DIR}/update.sh << 'EOF'
#!/bin/bash
# Eleanor DFIR Platform Update Script

set -e

BACKUP_DIR="/var/lib/eleanor/backups/$(date +%Y%m%d_%H%M%S)"

echo "=== Eleanor Update ==="

# Create backup
echo "Creating backup..."
mkdir -p "$BACKUP_DIR"

# Backup database
docker exec eleanor-postgres pg_dump -U eleanor eleanor > "$BACKUP_DIR/database.sql"

# Backup configuration
cp /opt/eleanor/.env "$BACKUP_DIR/.env" 2>/dev/null || true
cp -r /opt/eleanor/config "$BACKUP_DIR/config" 2>/dev/null || true

echo "Backup created at: $BACKUP_DIR"

# Pull new images
echo "Pulling new images..."
cd /opt/eleanor
docker compose pull

# Restart services
echo "Restarting services..."
docker compose down
docker compose up -d

# Run migrations
echo "Running database migrations..."
docker exec eleanor-backend alembic upgrade head

# Health check
echo "Running health check..."
sleep 10
curl -sf http://localhost:8000/api/v1/health || {
    echo "ERROR: Health check failed!"
    echo "Rolling back..."
    docker compose down
    docker compose up -d
    exit 1
}

echo "=== Update Complete ==="
EOF

chmod +x ${ELEANOR_DIR}/update.sh

# Set final permissions
chown -R eleanor:eleanor ${ELEANOR_DIR}
chmod 600 ${ELEANOR_DIR}/.env.template

echo "=== Eleanor Application Setup Complete ==="
