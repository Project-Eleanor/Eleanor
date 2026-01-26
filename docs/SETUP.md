# Eleanor Setup Guide

This guide covers the installation and initial configuration of Eleanor DFIR Platform.

## Table of Contents

- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [OVA Deployment](#ova-deployment)
- [Manual Installation](#manual-installation)
- [First Run Configuration](#first-run-configuration)
- [Verifying Installation](#verifying-installation)
- [Next Steps](#next-steps)

---

## Requirements

### Hardware Requirements

| Component | Minimum | Recommended | Production |
|-----------|---------|-------------|------------|
| CPU | 4 cores | 8 cores | 16+ cores |
| RAM | 8 GB | 16 GB | 32+ GB |
| Storage | 100 GB | 500 GB | 2+ TB SSD |
| Network | 1 Gbps | 1 Gbps | 10 Gbps |

### Software Requirements

- **Operating System**: Ubuntu 22.04 LTS or RHEL 8/9
- **Docker**: 24.0+ with Docker Compose v2
- **OpenSSL**: 1.1.1+ (for certificate generation)

### Network Requirements

| Port | Service | Description |
|------|---------|-------------|
| 80 | HTTP | Redirect to HTTPS |
| 443 | HTTPS | Main web interface |
| 5432 | PostgreSQL | Internal (can be exposed for external DB) |
| 9200 | Elasticsearch | Internal (can be exposed for external ES) |
| 6379 | Redis | Internal only |

---

## Quick Start

For a quick development setup:

```bash
# Clone the repository
git clone https://github.com/your-org/eleanor.git
cd eleanor

# Copy and edit configuration
cp .env.example .env
# Edit .env with your settings

# Start services
docker compose up -d

# Access Eleanor at http://localhost:4200
```

---

## OVA Deployment

### Importing the OVA

1. Download the Eleanor OVA from the releases page
2. Import into your virtualization platform:
   - **VMware**: File → Import → OVF or OVA
   - **VirtualBox**: File → Import Appliance
   - **Proxmox**: Create VM → Import from OVA

3. Allocate resources based on your needs (see Requirements)

4. Power on the VM and wait for boot

### First-Run Setup Wizard

On first boot, Eleanor runs an interactive setup wizard:

```bash
# The wizard starts automatically, or run manually:
/opt/eleanor/scripts/first-run-setup.sh
```

The wizard will:
1. Detect system resources
2. Prompt for hostname/IP
3. Create admin account
4. Select integrations to enable
5. Generate secure secrets
6. Create SSL certificates
7. Start all services
8. Display access information

### Post-Setup Steps

1. **Access the web interface** at `https://<hostname>`
2. **Accept the SSL certificate warning** (self-signed by default)
3. **Log in** with the admin credentials you created
4. **Configure integrations** in Settings → Integrations

---

## Manual Installation

### Step 1: Prerequisites

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y docker.io docker-compose-v2 openssl curl git

# Enable and start Docker
sudo systemctl enable docker
sudo systemctl start docker

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

### Step 2: Clone Repository

```bash
git clone https://github.com/your-org/eleanor.git /opt/eleanor
cd /opt/eleanor
```

### Step 3: Generate Secrets

```bash
./scripts/generate-secrets.sh --output secrets.env
source secrets.env
```

### Step 4: Create Configuration

```bash
cp .env.example .env

# Edit .env with your settings
# At minimum, set:
# - ELEANOR_HOSTNAME
# - SECRET_KEY (from secrets.env)
# - POSTGRES_PASSWORD (from secrets.env)
# - ADMIN_USERNAME
# - ADMIN_PASSWORD
# - ADMIN_EMAIL
```

### Step 5: Generate SSL Certificates

```bash
./scripts/generate-certs.sh --hostname your.hostname.com --output ./certificates
```

### Step 6: Start Services

```bash
# Development mode
docker compose up -d

# Production mode
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Step 7: Create Admin User

```bash
# Wait for services to be healthy
./scripts/health-check.sh --wait 120

# The admin user is created automatically if ADMIN_* env vars are set
# Otherwise, create manually:
docker exec eleanor-backend python -c "
from app.cli import create_admin
create_admin('admin', 'your-password', 'admin@example.com')
"
```

---

## First Run Configuration

### Accessing Eleanor

1. Open a browser and navigate to `https://<hostname>`
2. Accept the self-signed certificate warning
3. Log in with your admin credentials

### Initial Configuration Checklist

- [ ] Change admin password if using default
- [ ] Configure organization settings
- [ ] Set up integrations (Velociraptor, IRIS, etc.)
- [ ] Create additional user accounts
- [ ] Configure LDAP/OIDC if using SSO
- [ ] Set up email notifications
- [ ] Review security settings

### Configuring Integrations

Navigate to **Settings → Integrations** to configure:

#### Velociraptor
```
URL: https://your-velociraptor-server:8003
API Key: (from Velociraptor GUI → Server → API Clients)
```

#### IRIS
```
URL: https://your-iris-server:8443
API Key: (from IRIS → User Settings → API Key)
```

#### OpenCTI
```
URL: http://your-opencti-server:8080
API Key: (from OpenCTI → Settings → API Access)
```

#### Shuffle
```
URL: http://your-shuffle-server:3001
API Key: (from Shuffle → Settings → API)
```

#### Timesketch
```
URL: http://your-timesketch-server:5000
Username: (Timesketch admin user)
Password: (Timesketch admin password)
```

---

## Verifying Installation

### Health Check

Run the health check script to verify all services:

```bash
./scripts/health-check.sh
```

Expected output:
```
Eleanor Health Check Results
==============================

Core Services:
  [OK] postgres - Service responding
  [OK] elasticsearch - Cluster status: green
  [OK] redis - Service responding
  [OK] backend - API responding
  [OK] frontend - Frontend serving

Overall Status: HEALTHY
```

### Running Tests

```bash
# Run health check tests
cd backend
pytest tests/health -v

# Run full test suite
pytest tests/ -v
```

### Checking Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f elasticsearch
```

---

## Next Steps

After completing setup:

1. **Read the Configuration Guide**: `docs/CONFIGURATION.md`
2. **Set up backups**: `./scripts/backup.sh --help`
3. **Review security hardening**: Configure firewall, SSL certs
4. **Create user accounts**: Add analysts and investigators
5. **Import data**: Start ingesting evidence and creating cases

---

## Troubleshooting

See `docs/TROUBLESHOOTING.md` for common issues and solutions.

### Common Issues

**Services won't start**
```bash
# Check Docker status
docker compose ps
docker compose logs

# Check disk space
df -h

# Check memory
free -h
```

**Can't access web interface**
```bash
# Check if nginx is running
docker compose logs frontend

# Check ports
netstat -tlpn | grep -E '(80|443)'
```

**Database connection errors**
```bash
# Check postgres
docker compose logs postgres
docker exec eleanor-postgres pg_isready
```

---

## Support

- Documentation: `/docs/`
- Issues: https://github.com/your-org/eleanor/issues
- Email: support@eleanor.io
