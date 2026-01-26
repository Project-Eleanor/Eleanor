# Eleanor Troubleshooting Guide

Solutions to common issues with Eleanor DFIR Platform.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Installation Issues](#installation-issues)
- [Service Issues](#service-issues)
- [Authentication Issues](#authentication-issues)
- [Integration Issues](#integration-issues)
- [Performance Issues](#performance-issues)
- [Data Issues](#data-issues)
- [Getting Help](#getting-help)

---

## Quick Diagnostics

Run these commands first to understand the system state:

```bash
# Overall health check
./scripts/health-check.sh -v

# Service status
docker compose ps

# Recent logs
docker compose logs --tail=100

# System resources
free -h
df -h
docker system df
```

---

## Installation Issues

### Docker Compose Not Found

**Symptom**: `docker-compose: command not found`

**Solution**: Install Docker Compose v2

```bash
# Ubuntu/Debian
sudo apt install docker-compose-plugin

# Or standalone
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### Permission Denied (Docker)

**Symptom**: `Got permission denied while trying to connect to the Docker daemon`

**Solution**: Add user to docker group

```bash
sudo usermod -aG docker $USER
newgrp docker
# Or logout/login
```

### Port Already in Use

**Symptom**: `Error starting userland proxy: listen tcp4 0.0.0.0:80: bind: address already in use`

**Solution**: Find and stop the conflicting service

```bash
# Find what's using the port
sudo lsof -i :80
sudo netstat -tlpn | grep :80

# Stop the service or change Eleanor's port in docker-compose.yml
```

### Out of Disk Space

**Symptom**: Services fail to start, "no space left on device" errors

**Solution**: Clean up Docker and free space

```bash
# Remove unused Docker resources
docker system prune -a --volumes

# Check disk usage
df -h
du -sh /var/lib/docker/*

# Expand disk if using VM
```

---

## Service Issues

### Services Not Starting

**Symptom**: `docker compose ps` shows services as "Exit" or "Restarting"

**Diagnosis**:
```bash
# Check specific service logs
docker compose logs postgres
docker compose logs elasticsearch
docker compose logs backend
```

**Common Causes**:

1. **Missing environment variables**
   ```bash
   # Verify .env exists and is valid
   cat .env | grep -v '^#' | grep '='
   ```

2. **Database initialization failed**
   ```bash
   # Reset database
   docker compose down -v
   docker compose up -d
   ```

3. **Insufficient memory for Elasticsearch**
   ```bash
   # Reduce ES heap size in .env
   ES_JAVA_OPTS=-Xms512m -Xmx512m
   ```

### Backend Not Responding

**Symptom**: API returns 502 Bad Gateway or connection refused

**Diagnosis**:
```bash
# Check backend logs
docker compose logs backend

# Check if backend is running
docker compose exec backend curl http://localhost:8000/api/v1/health

# Check database connection
docker compose exec backend python -c "
from app.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    print(conn.execute(text('SELECT 1')).scalar())
"
```

**Common Causes**:

1. **Database not ready**
   ```bash
   # Wait for postgres
   docker compose exec postgres pg_isready -U eleanor
   ```

2. **Migration errors**
   ```bash
   # Run migrations manually
   docker compose exec backend alembic upgrade head
   ```

3. **Missing dependencies**
   ```bash
   # Rebuild backend
   docker compose build backend
   docker compose up -d backend
   ```

### Elasticsearch Cluster Red/Yellow

**Symptom**: Searches fail or are slow, cluster status not green

**Diagnosis**:
```bash
# Check cluster health
curl -s localhost:9200/_cluster/health?pretty

# Check indices
curl -s localhost:9200/_cat/indices?v

# Check shards
curl -s localhost:9200/_cat/shards?v | grep -v STARTED
```

**Solutions**:

1. **Single node yellow is normal**
   ```bash
   # Yellow status with replica shards unassigned is expected
   # for single-node clusters
   ```

2. **Red status - fix unassigned shards**
   ```bash
   # Retry allocation
   curl -X POST "localhost:9200/_cluster/reroute?retry_failed=true"
   ```

3. **Out of disk space**
   ```bash
   # Check watermarks
   curl -s localhost:9200/_cluster/settings?pretty | grep watermark

   # Free space or increase threshold
   ```

### Redis Connection Issues

**Symptom**: "Error connecting to Redis" in logs

**Diagnosis**:
```bash
# Test Redis connection
docker compose exec redis redis-cli ping

# Check Redis logs
docker compose logs redis
```

**Solution**:
```bash
# Restart Redis
docker compose restart redis

# If data corrupted, reset
docker compose down
docker volume rm eleanor_redis_data
docker compose up -d
```

---

## Authentication Issues

### Can't Log In

**Symptom**: Login fails with "Invalid credentials"

**Diagnosis**:
```bash
# Check if user exists
docker compose exec postgres psql -U eleanor -d eleanor -c "
SELECT username, email, is_active FROM users;
"
```

**Solutions**:

1. **Reset admin password**
   ```bash
   ./scripts/reset-admin-password.sh --user admin --generate
   ```

2. **User is disabled**
   ```bash
   docker compose exec postgres psql -U eleanor -d eleanor -c "
   UPDATE users SET is_active = true WHERE username = 'admin';
   "
   ```

3. **Password not hashed correctly**
   ```bash
   # Regenerate password hash
   ./scripts/reset-admin-password.sh --user admin
   ```

### OIDC/LDAP Issues

**Symptom**: SSO login fails

**Diagnosis**:
```bash
# Check backend logs during login attempt
docker compose logs backend --tail=50 -f
```

**Common Causes**:

1. **OIDC callback URL mismatch**
   ```bash
   # Verify OIDC_REDIRECT_URI matches IdP configuration
   grep OIDC .env
   ```

2. **LDAP bind failure**
   ```bash
   # Test LDAP connection
   ldapsearch -x -H ldap://dc.example.com \
     -D "CN=svc_eleanor,OU=Service,DC=example,DC=com" \
     -w "password" \
     -b "DC=example,DC=com" \
     "(sAMAccountName=testuser)"
   ```

3. **Certificate issues**
   ```bash
   # For LDAPS, check cert
   openssl s_client -connect dc.example.com:636
   ```

### JWT Token Issues

**Symptom**: "Token expired" or "Invalid token" errors

**Solutions**:

1. **Clear browser storage**
   - Clear localStorage and sessionStorage
   - Delete cookies

2. **Clock sync issue**
   ```bash
   # Check server time
   date

   # Sync with NTP
   sudo ntpdate pool.ntp.org
   ```

3. **SECRET_KEY changed**
   - All existing tokens become invalid
   - Users must log in again

---

## Integration Issues

### Velociraptor Connection Failed

**Symptom**: "Failed to connect to Velociraptor" error

**Diagnosis**:
```bash
# Test connection from backend
docker compose exec backend curl -k https://velociraptor:8003/api/status
```

**Solutions**:

1. **API key invalid**
   - Generate new API key in Velociraptor GUI
   - Update VELOCIRAPTOR_API_KEY in .env

2. **SSL certificate issues**
   ```bash
   # Disable SSL verification (for self-signed)
   VELOCIRAPTOR_VERIFY_SSL=false
   ```

3. **Network connectivity**
   ```bash
   # Check DNS resolution
   docker compose exec backend nslookup velociraptor

   # Check port
   docker compose exec backend nc -zv velociraptor 8003
   ```

### IRIS Sync Issues

**Symptom**: Cases not syncing to IRIS

**Diagnosis**:
```bash
# Check IRIS adapter logs
docker compose logs backend | grep -i iris
```

**Solutions**:

1. **API key permissions**
   - Ensure IRIS API key has write permissions

2. **Case type mismatch**
   - Verify case types are configured in IRIS

### OpenCTI Enrichment Failing

**Symptom**: No threat intel data returned

**Diagnosis**:
```bash
# Test OpenCTI GraphQL
curl -X POST http://opencti:8080/graphql \
  -H "Authorization: Bearer $OPENCTI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "{ indicators { edges { node { id } } } }"}'
```

**Solutions**:

1. **API token format**
   - Use the full token, not just UUID

2. **Connector not running**
   - Check OpenCTI connectors are importing data

---

## Performance Issues

### Slow Searches

**Symptom**: Elasticsearch searches taking >10 seconds

**Diagnosis**:
```bash
# Check cluster health
curl localhost:9200/_cluster/health?pretty

# Check slow log
curl localhost:9200/_cat/indices?v&s=store.size:desc
```

**Solutions**:

1. **Increase ES heap**
   ```bash
   ES_JAVA_OPTS=-Xms4g -Xmx4g
   ```

2. **Optimize indices**
   ```bash
   curl -X POST "localhost:9200/eleanor-*/_forcemerge?max_num_segments=1"
   ```

3. **Add query caching**
   ```bash
   curl -X PUT "localhost:9200/eleanor-*/_settings" -H 'Content-Type: application/json' -d'
   {"index": {"queries.cache.enabled": true}}
   '
   ```

### High Memory Usage

**Symptom**: OOM kills, swapping

**Diagnosis**:
```bash
docker stats
free -h
```

**Solutions**:

1. **Limit container memory**
   - Edit docker-compose.yml to add memory limits

2. **Reduce ES heap**
   ```bash
   ES_JAVA_OPTS=-Xms1g -Xmx1g
   ```

3. **Reduce backend workers**
   ```bash
   WORKERS=2
   ```

### Slow Database Queries

**Symptom**: API responses slow, database CPU high

**Diagnosis**:
```bash
# Check slow queries
docker compose exec postgres psql -U eleanor -d eleanor -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active'
ORDER BY duration DESC;
"
```

**Solutions**:

1. **Add missing indexes**
   ```bash
   # Run migrations
   docker compose exec backend alembic upgrade head
   ```

2. **Vacuum database**
   ```bash
   docker compose exec postgres psql -U eleanor -d eleanor -c "VACUUM ANALYZE;"
   ```

---

## Data Issues

### Evidence Upload Fails

**Symptom**: "Upload failed" error

**Diagnosis**:
```bash
# Check backend logs
docker compose logs backend | grep -i upload

# Check disk space
df -h
docker exec eleanor-backend df -h /app/evidence
```

**Solutions**:

1. **Increase upload limit**
   - Nginx: `client_max_body_size`
   - Backend: `MAX_UPLOAD_SIZE_MB`

2. **Permission issues**
   ```bash
   docker compose exec backend ls -la /app/evidence
   docker compose exec backend chmod 755 /app/evidence
   ```

### Database Backup/Restore Failed

**Symptom**: backup.sh or restore.sh errors

**Solutions**:

1. **Backup directory permissions**
   ```bash
   mkdir -p backups
   chmod 755 backups
   ```

2. **Container not running**
   ```bash
   # Start services first
   docker compose up -d postgres
   ```

3. **Corrupt backup**
   ```bash
   # Verify backup
   ./scripts/restore.sh --backup ./backups/latest --verify-only
   ```

---

## Getting Help

### Collecting Diagnostics

Before requesting help, gather:

```bash
# System info
uname -a
docker version
docker compose version

# Eleanor status
./scripts/health-check.sh --json > diagnostics.json
docker compose logs --tail=500 > logs.txt

# Configuration (remove secrets)
grep -v PASSWORD .env | grep -v SECRET | grep -v KEY > config.txt
```

### Support Channels

- **Documentation**: `/docs/` directory
- **Issues**: https://github.com/your-org/eleanor/issues
- **Email**: support@eleanor.io

### When Reporting Issues

Include:
1. Eleanor version
2. Operating system
3. Steps to reproduce
4. Expected vs actual behavior
5. Relevant logs
6. Configuration (without secrets)
