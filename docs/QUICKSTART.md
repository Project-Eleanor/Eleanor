# Eleanor Quick Start Guide

Get Eleanor DFIR platform running in minutes.

## Prerequisites

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 4 cores | 8 cores |
| RAM | 8 GB | 16 GB |
| Disk | 50 GB | 100 GB SSD |
| OS | Ubuntu 22.04, Debian 12, or macOS | Ubuntu 22.04 |

### Software Requirements

- **Docker** 24.0+ and **Docker Compose** v2
- **Git** (for cloning the repository)

```bash
# Install Docker (Ubuntu/Debian)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in for group changes

# Verify installation
docker --version
docker compose version
```

## Installation

### Step 1: Clone Repository

```bash
git clone https://github.com/your-org/Eleanor.git
cd Eleanor
```

### Step 2: Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration (optional - defaults work for development)
# nano .env
```

Key settings in `.env`:
```bash
# Security - Change in production!
SECRET_KEY=change-me-to-a-secure-random-string
POSTGRES_PASSWORD=your_secure_password

# Optional integrations (disabled by default)
VELOCIRAPTOR_ENABLED=false
IRIS_ENABLED=false
OPENCTI_ENABLED=false
```

### Step 3: Start Services

```bash
# Start all services
docker compose up -d

# Watch startup logs
docker compose logs -f

# Wait for services to be healthy (2-3 minutes)
docker compose ps
```

### Step 4: Create Admin User

```bash
# Create initial admin account
docker exec eleanor-backend python -m app.cli create-user \
  --username admin \
  --email admin@example.com \
  --password YourSecurePassword123! \
  --admin
```

## Access URLs

| Service | URL | Default Credentials |
|---------|-----|---------------------|
| **Web UI** | http://localhost:4200 | admin / (your password) |
| **API** | http://localhost:8000/api/v1 | JWT Bearer token |
| **API Docs** | http://localhost:8000/docs | - |
| **Elasticsearch** | http://localhost:9200 | - |

## First Steps

### 1. Log In to Web UI

1. Open http://localhost:4200 in your browser
2. Log in with your admin credentials
3. Navigate to the Dashboard

### 2. Upload Evidence

**Via Web UI:**
1. Go to **Evidence** > **Upload**
2. Select your evidence file (EVTX, JSON, etc.)
3. Associate with a case or create new case
4. Submit for parsing

**Via API:**
```bash
# Get JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YourPassword"}' | jq -r '.access_token')

# Upload evidence
curl -X POST http://localhost:8000/api/v1/evidence/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/Security.evtx" \
  -F "case_id=YOUR_CASE_ID"
```

### 3. Submit Parsing Job

```bash
# Submit parsing job for uploaded evidence
curl -X POST http://localhost:8000/api/v1/parsing/submit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "evidence_id": "YOUR_EVIDENCE_ID",
    "parser_hint": "windows_evtx"
  }'

# Check job status
curl http://localhost:8000/api/v1/parsing/jobs/JOB_ID \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Search Events

**Via Web UI:**
1. Go to **Search**
2. Enter your query (KQL or ES|QL syntax)
3. Select time range
4. Click Search

**Via API:**
```bash
# Search for authentication events
curl -X POST http://localhost:8000/api/v1/search/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "event.category:authentication",
    "indices": ["eleanor-events-*"],
    "size": 100
  }'
```

### 5. Create Detection Rule

```bash
curl -X POST http://localhost:8000/api/v1/analytics/rules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Failed Login Attempts",
    "description": "Detects multiple failed login attempts",
    "query": "event.action:user_logon_failed",
    "query_language": "kql",
    "severity": "medium",
    "enabled": true
  }'
```

## Supported Evidence Types

| Format | Parser | Extensions |
|--------|--------|------------|
| Windows Event Log | `windows_evtx` | .evtx |
| JSON/JSONL Logs | `json` | .json, .jsonl, .ndjson |
| Windows Registry | `windows_registry` | SAM, SYSTEM, SOFTWARE, NTUSER.DAT |
| Windows Prefetch | `prefetch` | .pf |
| MFT | `mft` | $MFT |
| Browser History | `browser_chrome`, `browser_firefox` | History, places.sqlite |
| Network Capture | `pcap` | .pcap, .pcapng |

List all available parsers:
```bash
curl http://localhost:8000/api/v1/parsing/parsers \
  -H "Authorization: Bearer $TOKEN"
```

## Common Tasks

### View Parsing Jobs

```bash
# List all parsing jobs
curl http://localhost:8000/api/v1/parsing/jobs \
  -H "Authorization: Bearer $TOKEN"
```

### Create Investigation Case

```bash
curl -X POST http://localhost:8000/api/v1/cases \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Incident 2026-001",
    "description": "Suspected data exfiltration",
    "severity": "high",
    "status": "open"
  }'
```

### Check Service Health

```bash
# Overall health
curl http://localhost:8000/api/v1/health

# Check individual services
docker compose ps
```

## Troubleshooting

### Services Not Starting

```bash
# Check container logs
docker compose logs backend
docker compose logs elasticsearch

# Ensure enough memory
free -h

# Reset and restart
docker compose down -v
docker compose up -d
```

### Cannot Access Web UI

1. Verify frontend is running: `docker compose ps frontend`
2. Check for port conflicts: `lsof -i :4200`
3. View frontend logs: `docker compose logs frontend`

### Parsing Job Stuck

```bash
# Check Celery worker logs
docker compose logs celery-worker

# Verify Redis connection
docker exec eleanor-redis redis-cli ping

# Restart Celery workers
docker compose restart celery-worker celery-beat
```

### Elasticsearch Issues

```bash
# Check cluster health
curl http://localhost:9200/_cluster/health?pretty

# Check indices
curl http://localhost:9200/_cat/indices?v

# View ES logs
docker compose logs elasticsearch
```

## Stopping Eleanor

```bash
# Stop all services (preserves data)
docker compose down

# Stop and remove all data
docker compose down -v
```

## Next Steps

- Read the [Configuration Guide](CONFIGURATION.md) for detailed settings
- Review [Production Deployment](PRODUCTION.md) for production setup
- Check [Troubleshooting Guide](TROUBLESHOOTING.md) for common issues

## Getting Help

- GitHub Issues: Report bugs and request features
- Documentation: `/docs` directory in repository
