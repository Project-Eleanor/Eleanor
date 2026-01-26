# Eleanor Configuration Reference

Complete reference for all Eleanor configuration options.

## Table of Contents

- [Environment Variables](#environment-variables)
- [Core Settings](#core-settings)
- [Database](#database)
- [Elasticsearch](#elasticsearch)
- [Redis](#redis)
- [Security](#security)
- [Authentication](#authentication)
- [Integrations](#integrations)
- [Email](#email)
- [Advanced Settings](#advanced-settings)

---

## Environment Variables

Eleanor is configured via environment variables, typically stored in a `.env` file at the project root. The `first-run-setup.sh` script generates this file automatically.

### File Locations

| File | Purpose |
|------|---------|
| `.env` | Active configuration |
| `.env.example` | Template with defaults |
| `.env.ova.template` | OVA deployment template |

---

## Core Settings

### ELEANOR_HOSTNAME

**Required**: Yes
**Default**: `localhost`

The hostname or IP address of the Eleanor server. Used for CORS, SSL certificates, and generating URLs.

```bash
ELEANOR_HOSTNAME=eleanor.example.com
```

### SECRET_KEY

**Required**: Yes
**Default**: None (must be set)

Secret key for cryptographic operations (JWT signing, session encryption). Generate with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

```bash
SECRET_KEY=your-secure-random-string
```

### DEBUG

**Required**: No
**Default**: `false`

Enable debug mode. **Never enable in production**.

```bash
DEBUG=false
```

### LOG_LEVEL

**Required**: No
**Default**: `INFO`

Logging verbosity. Options: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

```bash
LOG_LEVEL=INFO
```

---

## Database

### DATABASE_URL

**Required**: Yes
**Default**: `postgresql://eleanor:password@postgres:5432/eleanor`

PostgreSQL connection string.

```bash
DATABASE_URL=postgresql://eleanor:${POSTGRES_PASSWORD}@postgres:5432/eleanor
```

### POSTGRES_PASSWORD

**Required**: Yes
**Default**: None

Password for the PostgreSQL `eleanor` user.

```bash
POSTGRES_PASSWORD=your-secure-password
```

### Database Connection Pool

```bash
# Maximum connections in pool
DB_POOL_SIZE=10

# Overflow connections
DB_MAX_OVERFLOW=20

# Connection recycle time (seconds)
DB_POOL_RECYCLE=3600
```

---

## Elasticsearch

### ELASTICSEARCH_URL

**Required**: Yes
**Default**: `http://localhost:9200`

Elasticsearch cluster URL.

```bash
ELASTICSEARCH_URL=http://elasticsearch:9200
```

### ELASTICSEARCH_PASSWORD

**Required**: No
**Default**: None

Password for Elasticsearch (if security is enabled).

```bash
ELASTICSEARCH_PASSWORD=elastic-password
```

### ES_JAVA_OPTS

**Required**: No
**Default**: `-Xms1g -Xmx1g`

JVM heap size for Elasticsearch. Set to 50% of available RAM, max 31GB.

```bash
ES_JAVA_OPTS=-Xms4g -Xmx4g
```

---

## Redis

### REDIS_URL

**Required**: Yes
**Default**: `redis://localhost:6379`

Redis connection URL.

```bash
REDIS_URL=redis://redis:6379
```

### REDIS_PASSWORD

**Required**: No
**Default**: None

Password for Redis (if AUTH is enabled).

```bash
REDIS_PASSWORD=redis-password
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379
```

---

## Security

### JWT_ALGORITHM

**Required**: No
**Default**: `HS256`

JWT signing algorithm. Options: `HS256`, `HS384`, `HS512`, `RS256`

```bash
JWT_ALGORITHM=HS256
```

### JWT_EXPIRE_MINUTES

**Required**: No
**Default**: `60`

JWT token expiration time in minutes.

```bash
JWT_EXPIRE_MINUTES=60
```

### CORS_ORIGINS

**Required**: No
**Default**: `*` (in dev), `https://${ELEANOR_HOSTNAME}` (in prod)

Allowed CORS origins. Comma-separated list.

```bash
CORS_ORIGINS=https://eleanor.example.com,https://admin.example.com
```

### Session Settings

```bash
# Session timeout (minutes)
SESSION_TIMEOUT_MINUTES=480

# Max concurrent sessions per user
MAX_CONCURRENT_SESSIONS=5
```

### Rate Limiting

```bash
# Enable rate limiting
RATE_LIMIT_ENABLED=true

# Requests per period
RATE_LIMIT_REQUESTS=100

# Period in seconds
RATE_LIMIT_PERIOD=60
```

---

## Authentication

### Local Accounts (SAM)

```bash
# Enable local account authentication
SAM_ENABLED=true

# Allow self-registration
SAM_ALLOW_REGISTRATION=false
```

### Initial Admin Account

```bash
# Created on first run
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure-password
ADMIN_EMAIL=admin@example.com
```

### OIDC / OAuth2

For Azure AD, Okta, Keycloak, Auth0, etc.

```bash
OIDC_ENABLED=true
OIDC_ISSUER=https://login.microsoftonline.com/{tenant}/v2.0
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_REDIRECT_URI=https://eleanor.example.com/auth/callback

# Optional: Scopes
OIDC_SCOPES=openid,profile,email

# Optional: Claim mappings
OIDC_USERNAME_CLAIM=preferred_username
OIDC_EMAIL_CLAIM=email
OIDC_NAME_CLAIM=name
```

### LDAP / Active Directory

```bash
LDAP_ENABLED=true
LDAP_SERVER=ldap://dc.example.com:389
LDAP_USE_SSL=false
LDAP_BASE_DN=DC=example,DC=com

# Bind credentials (for searching)
LDAP_BIND_DN=CN=svc_eleanor,OU=Service,DC=example,DC=com
LDAP_BIND_PASSWORD=bind-password

# Search filters
LDAP_USER_FILTER=(sAMAccountName={username})
LDAP_GROUP_FILTER=(member={user_dn})

# Group mappings
LDAP_ADMIN_GROUP=CN=Eleanor-Admins,OU=Groups,DC=example,DC=com
LDAP_ANALYST_GROUP=CN=Eleanor-Analysts,OU=Groups,DC=example,DC=com
```

---

## Integrations

### Velociraptor

```bash
VELOCIRAPTOR_ENABLED=true
VELOCIRAPTOR_URL=https://velociraptor:8003
VELOCIRAPTOR_API_KEY=your-api-key
VELOCIRAPTOR_VERIFY_SSL=false

# For mutual TLS
VELOCIRAPTOR_CLIENT_CERT=/path/to/client.crt
VELOCIRAPTOR_CLIENT_KEY=/path/to/client.key
```

### IRIS

```bash
IRIS_ENABLED=true
IRIS_URL=https://iris:8443
IRIS_API_KEY=your-api-key
IRIS_VERIFY_SSL=false

# Embedded IRIS settings
IRIS_DB_PASSWORD=iris-db-password
IRIS_SECRET_KEY=iris-secret
IRIS_PASSWORD_SALT=iris-salt
IRIS_ADMIN_PASSWORD=iris-admin-password
```

### OpenCTI

```bash
OPENCTI_ENABLED=true
OPENCTI_URL=http://opencti:8080
OPENCTI_API_KEY=your-api-token
OPENCTI_VERIFY_SSL=false

# Embedded OpenCTI settings
OPENCTI_ADMIN_EMAIL=admin@example.com
OPENCTI_ADMIN_PASSWORD=opencti-password
OPENCTI_ADMIN_TOKEN=uuid-token
```

### Shuffle

```bash
SHUFFLE_ENABLED=true
SHUFFLE_URL=http://shuffle:3001
SHUFFLE_API_KEY=your-api-key
SHUFFLE_VERIFY_SSL=false

# Embedded Shuffle settings
SHUFFLE_ADMIN_USER=admin
SHUFFLE_ADMIN_PASSWORD=shuffle-password
```

### Timesketch

```bash
TIMESKETCH_ENABLED=true
TIMESKETCH_URL=http://timesketch:5000
TIMESKETCH_USERNAME=admin
TIMESKETCH_PASSWORD=timesketch-password
TIMESKETCH_VERIFY_SSL=false

# Embedded Timesketch settings
TIMESKETCH_DB_PASSWORD=ts-db-password
TIMESKETCH_SECRET_KEY=ts-secret
```

---

## Email

```bash
SMTP_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=eleanor@example.com
SMTP_PASSWORD=smtp-password
SMTP_FROM=Eleanor DFIR <eleanor@example.com>
SMTP_TLS=true
```

---

## Advanced Settings

### Evidence Storage

```bash
# Storage path
EVIDENCE_PATH=/app/evidence

# Max upload size (bytes)
MAX_UPLOAD_SIZE_MB=10240

# Allowed extensions
ALLOWED_EVIDENCE_EXTENSIONS=.zip,.7z,.tar,.gz,.raw,.dd,.E01,.vmdk,.ova,.evtx,.pcap,.pcapng

# Encryption key for evidence at rest
EVIDENCE_ENCRYPTION_KEY=hex-encoded-key
```

### Search Settings

```bash
# Max search results
SEARCH_MAX_RESULTS=10000

# Search timeout
SEARCH_TIMEOUT_SECONDS=30
```

### Audit Logging

```bash
# Enable audit logging
AUDIT_LOG_ENABLED=true

# Retention period (days)
AUDIT_LOG_RETENTION_DAYS=365
```

### Monitoring

```bash
# Prometheus metrics
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Health check endpoint
HEALTH_CHECK_ENABLED=true
```

---

## Docker Compose Profiles

Eleanor uses Docker Compose profiles to separate environments:

```bash
# Development (default)
docker compose up -d

# Production
docker compose --profile prod up -d

# With backup service
docker compose --profile backup up -d

# All profiles
docker compose --profile prod --profile backup up -d
```

---

## Configuration Files Reference

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base Docker configuration |
| `docker-compose.prod.yml` | Production overrides |
| `docker-compose.tools.yml` | Embedded integration tools |
| `deploy/nginx/nginx.prod.conf` | Nginx production config |
| `deploy/docker/init-db.sql` | Database initialization |
| `certificates/` | SSL certificates |

---

## Security Best Practices

1. **Never commit `.env` to version control**
2. **Use strong, unique passwords** for all services
3. **Enable HTTPS** in production
4. **Restrict network access** to internal services
5. **Enable rate limiting** for API endpoints
6. **Configure proper CORS** origins
7. **Use LDAP/OIDC** for enterprise authentication
8. **Regular backups** with `./scripts/backup.sh`
9. **Monitor logs** for suspicious activity
10. **Keep dependencies updated**
